-- =============================================================
-- Migration 036 — Audit qualità parsing AIFA
-- =============================================================
--
-- Contesto:
--   Dopo i fix parser delle migration 031-035, restano due categorie
--   di "rumore" nei dati:
--   (a) ~772 packages legacy con strength_text == descrizione completa
--       (residuo storico di una vecchia versione del parser con
--        fallback "se non riesci a parsare metti tutto");
--   (b) ~18.977 packages omeopatici con strength_text valorizzato
--       (es. "800 MG" estratto dal peso della capsula vuota, non
--        dalla dose terapeutica) — per gli omeopatici la "dose" è
--        la potenza hahnemanniana (6K, 12K, MK), non un MG.
--
--   Questa migration:
--   1) Pulisce (a) e (b) one-shot via UPDATE.
--   2) Introduce la materialized view `catalog_it_packages_audit`
--      con un `quality_code` per ogni package, consultabile dopo
--      ogni re-import per misurare la qualità del parsing.
--   3) Aggiunge la RPC `refresh_catalog_audit()` (service-role)
--      da chiamare in coda a `refresh_catalog_variants()`.
--
--   La view è "additive" — niente modifiche sui dati esistenti
--   tranne le UPDATE legacy/omeopatici. Backward compat totale.
-- =============================================================

BEGIN;

-- ─── (a) Cleanup polluted-legacy: strength_text == descrizione ──
-- 772 packages dove qualche versione storica ha messo l'intera
-- descrizione come strength_text. Tornano a NULL: il vero strength
-- verrà ri-popolato (se possibile) al prossimo re-import dal CSV.
UPDATE catalog_it_packages
SET strength_text  = NULL,
    strength_value = NULL,
    strength_unit  = NULL
WHERE strength_text = descrizione;


-- ─── (b) Cleanup omeopatici: strength sempre NULL ───────────────
-- Per i farmaci omeopatici (tipo_procedura = 'Omeopatico') il
-- parser cattura un MG che è in realtà il peso della capsula
-- vuota (es. "CAPSULE DA 800 MG") o un riferimento accessorio.
-- La dose terapeutica omeopatica è la potenza hahnemanniana
-- (6K, 12K, 30K, 200K, MK), non un MG ponderale. Decisione:
-- per omeopatici strength_text resta NULL, e nella UI la
-- visualizzazione si baserà su forma + package_type.
UPDATE catalog_it_packages pkg
SET strength_text  = NULL,
    strength_value = NULL,
    strength_unit  = NULL
FROM catalog_it_products p
WHERE p.cod_farmaco = pkg.cod_farmaco
  AND p.tipo_procedura = 'Omeopatico'
  AND pkg.strength_text IS NOT NULL;


-- ─── Materialized view: catalog_it_packages_audit ──────────────
DROP MATERIALIZED VIEW IF EXISTS catalog_it_packages_audit CASCADE;

CREATE MATERIALIZED VIEW catalog_it_packages_audit AS
WITH base AS (
    SELECT
        pkg.codice_aic,
        pkg.cod_farmaco,
        pkg.descrizione,
        pkg.forma,
        pkg.strength_text,
        pkg.strength_value,
        pkg.strength_unit,
        pkg.unit_count,
        pkg.package_type,
        pkg.volume_value,
        pkg.volume_unit,
        pkg.fornitura_code,
        p.tipo_procedura,
        p.denominazione AS denominazione_prodotto
    FROM catalog_it_packages pkg
    LEFT JOIN catalog_it_products p ON p.cod_farmaco = pkg.cod_farmaco
    WHERE pkg.stato_amministrativo = 'Autorizzata'
      AND pkg.fornitura_code IN ('RR','RNR','RRL','RNRL','SOP','OTC','RMR')
)
SELECT
    codice_aic, cod_farmaco, denominazione_prodotto, forma, tipo_procedura,
    descrizione, strength_text, strength_value, strength_unit,
    unit_count, package_type, volume_value, volume_unit, fornitura_code,
    length(COALESCE(strength_text, '')) AS strength_len,
    -- Quality code: priorità alle categorie più specifiche
    CASE
        WHEN strength_text IS NOT NULL AND strength_text = descrizione
            THEN 'POLLUTED_LEGACY'
        WHEN tipo_procedura = 'Omeopatico'
            THEN 'OMEOPATICO'  -- intenzionalmente NULL post-fix migration 036
        WHEN strength_text IS NOT NULL AND length(strength_text) > 30
            THEN 'TRUNCATED'
        WHEN strength_text IS NULL
             AND descrizione ~* '\d+\s*(MG|MCG|MILLIGRAMM|MICROGRAMM|UI|U\.I\.|IU|MMOL|%)\b'
            THEN 'UNPARSED_BUG'
        WHEN strength_text IS NULL
            THEN 'UNPARSED_LEGITIMATE'
        WHEN package_type IS NULL
             AND forma ~* 'compress|capsul|bustin|fial|cerott|supposta|ovul|flacon|tubo|siring'
            THEN 'MISSING_PACKAGE_TYPE'
        WHEN strength_text IS NOT NULL
            THEN 'PARSED_OK'
        ELSE 'OTHER'
    END AS quality_code,
    -- Flag diagnostici aggiuntivi (utili per drill-down)
    (descrizione ~* '\d+\s*K\b' AND forma ~* 'capsul|granul|globul') AS flag_k_potency,
    (descrizione ~ ' mg - ') AS flag_dash_lowercase,
    (descrizione ~ ' \+ ' AND descrizione ~ '/') AS flag_combo_with_slash
FROM base
WITH DATA;

CREATE UNIQUE INDEX idx_catalog_audit_aic ON catalog_it_packages_audit (codice_aic);
CREATE INDEX idx_catalog_audit_quality ON catalog_it_packages_audit (quality_code);
CREATE INDEX idx_catalog_audit_forma ON catalog_it_packages_audit (forma);
CREATE INDEX idx_catalog_audit_cod_farmaco ON catalog_it_packages_audit (cod_farmaco);

COMMENT ON MATERIALIZED VIEW catalog_it_packages_audit IS
    'Audit qualità parsing AIFA: 1 riga per package pubblico autorizzato '
    'con quality_code categorico. Refresh via refresh_catalog_audit() in '
    'coda a refresh_catalog_variants(). Migration 036.';


-- ─── RPC refresh ────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.refresh_catalog_audit()
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY catalog_it_packages_audit;
END;
$$;

COMMENT ON FUNCTION public.refresh_catalog_audit IS
    'Refresh CONCURRENTLY della view catalog_it_packages_audit. Chiamato '
    'dopo refresh_catalog_variants() in import_aifa_csv.py. Migration 036.';

REVOKE EXECUTE ON FUNCTION public.refresh_catalog_audit FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.refresh_catalog_audit TO service_role;


-- ─── Grants di lettura ──────────────────────────────────────────
GRANT SELECT ON catalog_it_packages_audit TO authenticated;
REVOKE ALL ON catalog_it_packages_audit FROM PUBLIC, anon;

COMMIT;
