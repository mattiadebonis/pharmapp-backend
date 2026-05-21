-- =============================================================
-- Migration 037 — RPC audit_get_report()
-- =============================================================
--
-- Aggiunge una funzione server-side che restituisce in un'unica
-- chiamata il report di qualità del parsing AIFA: distribuzione
-- per quality_code + count per ogni validation rule + V13 rate.
--
-- Usata da `scripts/audit_catalog_quality.py`: client minimale che
-- formatta il JSON in Markdown. Niente DB connection diretta.
-- =============================================================

BEGIN;

CREATE OR REPLACE FUNCTION public.audit_get_report()
RETURNS jsonb
LANGUAGE plpgsql
STABLE
SET search_path = public, pg_temp
AS $$
DECLARE
    total_packages INTEGER;
    qc_distribution JSONB;
    rule_counts JSONB;
    v13_total_eligible INTEGER;
    v13_parsed_ok INTEGER;
    v13_rate NUMERIC;
BEGIN
    -- Totale packages pubblici autorizzati (= righe della view audit)
    SELECT COUNT(*) INTO total_packages FROM catalog_it_packages_audit;

    -- Distribuzione per quality_code
    SELECT jsonb_object_agg(quality_code, count) INTO qc_distribution
    FROM (
        SELECT quality_code, COUNT(*) AS count
        FROM catalog_it_packages_audit
        GROUP BY quality_code
    ) sub;

    -- Validation rules V01..V12 (counts)
    WITH violation_counts AS (
        SELECT 'V01' AS rule_id, COUNT(*) AS count FROM catalog_it_packages_audit
        WHERE forma ~* 'compress|capsul|bustin|fial'
          AND descrizione ~* '\d+\s*(MG|MCG|MILLIGRAMM|MICROGRAMM|UI|%)\b'
          AND strength_text IS NULL
          AND tipo_procedura IS DISTINCT FROM 'Omeopatico'
        UNION ALL
        SELECT 'V02', COUNT(*) FROM catalog_it_packages_audit
        WHERE strength_text IS NOT NULL AND length(strength_text) > 60
        UNION ALL
        SELECT 'V03', COUNT(*) FROM catalog_it_packages_audit
        WHERE strength_text IS NOT NULL AND strength_text = descrizione
        UNION ALL
        SELECT 'V04', COUNT(*) FROM catalog_it_packages_audit
        WHERE strength_value IS NOT NULL AND strength_text IS NULL
        UNION ALL
        SELECT 'V05', COUNT(*) FROM catalog_it_packages_audit
        WHERE strength_unit IS NOT NULL AND strength_unit <> ''
          AND strength_value IS NULL
        UNION ALL
        SELECT 'V06', COUNT(*) FROM catalog_it_packages_audit
        WHERE forma ~* 'compress' AND unit_count = 1
          AND descrizione ~* '\d{2,}\s*compress'
        UNION ALL
        SELECT 'V07', COUNT(*) FROM catalog_it_packages_audit
        WHERE package_type IS NULL
          AND forma ~* 'compress|capsul|bustin|fial|cerott|supposta|ovul|flacon|tubo|siring'
        UNION ALL
        SELECT 'V08', COUNT(*) FROM catalog_it_packages_audit
        WHERE forma ~* 'sciropp|sospens|soluzione orale|gocce orali'
          AND volume_value IS NULL
        UNION ALL
        SELECT 'V09', COUNT(*) FROM catalog_it_packages_audit
        WHERE strength_unit IS NOT NULL AND strength_unit <> ''
          AND upper(strength_unit) NOT IN (
            'MG','MCG','NG','PG','G','ML','L','UI','U.I.','IU','MMOL','MEQ','U','%',
            'MG/ML','MCG/ML','NG/ML','UI/ML','MEQ/ML','MG/L','MCG/L',
            'IU/ML','G/L','G/ML','PG/ML','MMOL/L',
            'MG/ORA','MCG/ORA','MG/H','MCG/H',
            'MG/EROGAZIONE','MCG/EROGAZIONE','MG/DOSE','MCG/DOSE',
            'MG/INALAZIONE','MCG/INALAZIONE',
            'MG/24H','MCG/24H','MG/72H','MCG/72H',
            'MG/ATTUAZIONE','MCG/ATTUAZIONE',
            -- Composte con denom numerico (Briladona, Augmentin ecc.) — pattern X/YUNIT
            -- Le accettiamo via regex check, ma in whitelist semplice non possiamo
            -- enumerarle tutte. Per ora: se contiene "/" e numero, accettiamola.
            -- Strategia: il check di whitelist usa LIKE per fallback.
            ''
          )
          AND NOT (strength_unit ~ '/[0-9]')  -- accetta unità composte con denom numerico
        UNION ALL
        SELECT 'V10', COUNT(*) FROM catalog_it_packages_audit
        WHERE tipo_procedura = 'Omeopatico' AND strength_text IS NOT NULL
        UNION ALL
        SELECT 'V11', COUNT(*) FROM catalog_it_packages_audit
        WHERE strength_text IS NOT NULL AND strength_text !~ '^[0-9]'
        UNION ALL
        SELECT 'V12', COUNT(*) FROM (
            SELECT cod_farmaco, forma
            FROM catalog_it_packages_audit
            WHERE tipo_procedura IS DISTINCT FROM 'Omeopatico'
            GROUP BY cod_farmaco, forma
            HAVING COUNT(*) FILTER (WHERE strength_text IS NULL) > 0
               AND COUNT(*) FILTER (WHERE strength_text IS NOT NULL) > 0
        ) inconsistent
    )
    SELECT jsonb_object_agg(rule_id, count) INTO rule_counts FROM violation_counts;

    -- V13: rate di parsing su "deve-avere-dose"
    SELECT
        COUNT(*),
        COUNT(*) FILTER (WHERE strength_text IS NOT NULL)
    INTO v13_total_eligible, v13_parsed_ok
    FROM catalog_it_packages_audit
    WHERE forma ~* 'compress|capsul|bustin|fial'
      AND descrizione ~* '\d+\s*(MG|MCG|MILLIGRAMM|MICROGRAMM|UI|%)\b'
      AND tipo_procedura IS DISTINCT FROM 'Omeopatico';

    v13_rate := CASE WHEN v13_total_eligible > 0
                     THEN round(100.0 * v13_parsed_ok / v13_total_eligible, 2)
                     ELSE 100 END;

    RETURN jsonb_build_object(
        'total_packages', total_packages,
        'quality_code_distribution', qc_distribution,
        'rule_counts', rule_counts,
        'v13', jsonb_build_object(
            'total_eligible', v13_total_eligible,
            'parsed_ok', v13_parsed_ok,
            'rate_pct', v13_rate,
            'pass', v13_rate >= 97.0
        ),
        'generated_at', now()
    );
END;
$$;

COMMENT ON FUNCTION public.audit_get_report IS
    'Audit qualità parsing AIFA: ritorna JSON con distribuzione quality_code, '
    'counts per validation rules V01-V12 e V13 rate. Migration 037.';

GRANT EXECUTE ON FUNCTION public.audit_get_report TO authenticated, service_role;


-- ─── RPC per drill-down: esempi per violation rule ──────────────
--
-- Restituisce fino a `p_limit` esempi (codice_aic, denominazione,
-- descrizione, strength_text, forma) per una specifica regola.
-- Solo regole con SELECT ben definite. Le altre ritornano [].
CREATE OR REPLACE FUNCTION public.audit_rule_examples(p_rule_id TEXT, p_limit INT DEFAULT 10)
RETURNS jsonb
LANGUAGE plpgsql
STABLE
SET search_path = public, pg_temp
AS $$
DECLARE
    result JSONB;
BEGIN
    CASE p_rule_id
        WHEN 'V01' THEN
            SELECT jsonb_agg(row_to_json(t)) INTO result FROM (
                SELECT codice_aic, denominazione_prodotto, LEFT(descrizione, 100) AS descrizione,
                       strength_text, forma
                FROM catalog_it_packages_audit
                WHERE forma ~* 'compress|capsul|bustin|fial'
                  AND descrizione ~* '\d+\s*(MG|MCG|MILLIGRAMM|MICROGRAMM|UI|%)\b'
                  AND strength_text IS NULL
                  AND tipo_procedura IS DISTINCT FROM 'Omeopatico'
                LIMIT p_limit
            ) t;
        WHEN 'V02' THEN
            SELECT jsonb_agg(row_to_json(t)) INTO result FROM (
                SELECT codice_aic, denominazione_prodotto, strength_text, length(strength_text) AS len, forma
                FROM catalog_it_packages_audit
                WHERE strength_text IS NOT NULL AND length(strength_text) > 60
                ORDER BY length(strength_text) DESC
                LIMIT p_limit
            ) t;
        WHEN 'V03' THEN
            SELECT jsonb_agg(row_to_json(t)) INTO result FROM (
                SELECT codice_aic, denominazione_prodotto, LEFT(strength_text, 100) AS strength_text
                FROM catalog_it_packages_audit
                WHERE strength_text IS NOT NULL AND strength_text = descrizione
                LIMIT p_limit
            ) t;
        WHEN 'V09' THEN
            SELECT jsonb_agg(row_to_json(t)) INTO result FROM (
                SELECT codice_aic, denominazione_prodotto, strength_text, strength_unit, forma
                FROM catalog_it_packages_audit
                WHERE strength_unit IS NOT NULL AND strength_unit <> ''
                  AND upper(strength_unit) NOT IN (
                    'MG','MCG','NG','PG','G','ML','L','UI','U.I.','IU','MMOL','MEQ','U','%',
                    'MG/ML','MCG/ML','NG/ML','UI/ML','MEQ/ML','MG/L','MCG/L',
                    'IU/ML','G/L','G/ML','PG/ML','MMOL/L'
                  )
                  AND NOT (strength_unit ~ '/[0-9]')
                LIMIT p_limit
            ) t;
        WHEN 'V10' THEN
            SELECT jsonb_agg(row_to_json(t)) INTO result FROM (
                SELECT codice_aic, denominazione_prodotto, strength_text, forma
                FROM catalog_it_packages_audit
                WHERE tipo_procedura = 'Omeopatico' AND strength_text IS NOT NULL
                LIMIT p_limit
            ) t;
        WHEN 'V11' THEN
            SELECT jsonb_agg(row_to_json(t)) INTO result FROM (
                SELECT codice_aic, denominazione_prodotto, strength_text, forma
                FROM catalog_it_packages_audit
                WHERE strength_text IS NOT NULL AND strength_text !~ '^[0-9]'
                LIMIT p_limit
            ) t;
        ELSE
            result := '[]'::jsonb;
    END CASE;

    RETURN COALESCE(result, '[]'::jsonb);
END;
$$;

COMMENT ON FUNCTION public.audit_rule_examples IS
    'Drill-down su violazione rule: ritorna esempi packages. Migration 037.';

GRANT EXECUTE ON FUNCTION public.audit_rule_examples TO authenticated, service_role;

COMMIT;
