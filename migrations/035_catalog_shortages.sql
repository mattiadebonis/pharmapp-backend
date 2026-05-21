-- =============================================================
-- Migration 035 — Carenze farmaci AIFA
-- =============================================================
--
-- Contesto:
--   AIFA pubblica l'elenco dei farmaci carenti (temporaneamente
--   non disponibili) su https://www.aifa.gov.it/farmaci-carenti.
--   La pagina espone una tabella HTML con righe per AIC:
--     - Principio attivo
--     - Denominazione
--     - Confezione (AIC)
--     - Motivazione carenza
--     - Data inizio carenza
--     - Data fine prevista
--     - Eventuali farmaci sostitutivi
--
--   Costruiamo una tabella `catalog_it_shortages` indicizzata per
--   codice_aic e cod_farmaco. Il popolamento è via
--   scripts/scrape_aifa_carenze.py, che va eseguito
--   periodicamente (es. cron giornaliero).
--
--   Update RPC fetch_catalog_product_v1 / fetch_catalog_package_v1
--   per esporre lo stato di carenza al client iOS.
-- =============================================================

BEGIN;

-- ─── Tabella catalog_it_shortages ────────────────────────────────
CREATE TABLE IF NOT EXISTS catalog_it_shortages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    codice_aic TEXT NOT NULL,
    -- cod_farmaco è denormalizzato (estraibile da codice_aic via
    -- LEFT(codice_aic, 6)) ma popolato in fase di scrape per query
    -- "tutte le carenze del prodotto X" senza join.
    cod_farmaco TEXT NOT NULL,
    -- Motivazione AIFA (testo libero in italiano)
    reason TEXT,
    -- Date come testo perché AIFA a volte usa formati misti
    -- (gg/mm/aaaa, "in attesa", "non comunicata"). Normalizziamo
    -- a ISO quando possibile, altrimenti NULL.
    start_date DATE,
    expected_end_date DATE,
    -- Eventuali sostitutivi indicati da AIFA (lista AIC separati
    -- da virgola). Testo libero per ora.
    substitutes TEXT,
    -- Snapshot della pagina scraper: utile per debug se il parser
    -- cambia in futuro.
    source_url TEXT,
    -- Audit trail
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Lo scraper può marcare una carenza come "risolta" quando
    -- non appare più nell'elenco AIFA. La riga rimane per storico.
    resolved_at TIMESTAMPTZ,
    CONSTRAINT catalog_it_shortages_uniq UNIQUE (codice_aic, start_date)
);

CREATE INDEX IF NOT EXISTS idx_catalog_it_shortages_aic
    ON catalog_it_shortages (codice_aic);
CREATE INDEX IF NOT EXISTS idx_catalog_it_shortages_cod
    ON catalog_it_shortages (cod_farmaco);
CREATE INDEX IF NOT EXISTS idx_catalog_it_shortages_active
    ON catalog_it_shortages (cod_farmaco)
    WHERE resolved_at IS NULL;

COMMENT ON TABLE catalog_it_shortages IS
    'Carenze farmaci AIFA. Popolata da scripts/scrape_aifa_carenze.py. '
    'resolved_at NULL = carenza ancora attiva. Migration 035.';


-- ─── RLS ─────────────────────────────────────────────────────────
ALTER TABLE catalog_it_shortages ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS catalog_it_shortages_read ON catalog_it_shortages;
CREATE POLICY catalog_it_shortages_read ON catalog_it_shortages
    FOR SELECT TO authenticated USING (true);

GRANT SELECT ON catalog_it_shortages TO authenticated;
REVOKE ALL ON catalog_it_shortages FROM anon;


-- ─── RPC: fetch_shortages_for_product ────────────────────────────
--
-- Restituisce le carenze attive (resolved_at IS NULL) per un
-- prodotto. Ordinate dal più recente.
CREATE OR REPLACE FUNCTION public.fetch_shortages_for_product(
    p_country TEXT,
    p_product_id TEXT
) RETURNS JSONB
LANGUAGE plpgsql
STABLE
SET search_path = public, pg_temp
AS $$
DECLARE
    result JSONB;
BEGIN
    IF p_country <> 'it' THEN
        RETURN '[]'::jsonb;
    END IF;

    SELECT COALESCE(jsonb_agg(
        jsonb_build_object(
            'codice_aic', codice_aic,
            'reason', reason,
            'start_date', start_date,
            'expected_end_date', expected_end_date,
            'substitutes', substitutes
        ) ORDER BY start_date DESC NULLS LAST
    ), '[]'::jsonb)
    INTO result
    FROM catalog_it_shortages
    WHERE cod_farmaco = p_product_id
      AND resolved_at IS NULL;

    RETURN result;
END;
$$;

GRANT EXECUTE ON FUNCTION public.fetch_shortages_for_product(TEXT, TEXT) TO authenticated;


-- ─── Aggiorna fetch_catalog_product_v1 per esporre carenze ───────
--
-- Aggiungiamo due campi al payload prodotto:
--   - `has_active_shortage` (bool): true se almeno una pkg è
--     attualmente carente. Pensato per badge / warning.
--   - `shortages` (array): elenco completo carenze attive (stessa
--     forma di fetch_shortages_for_product).
CREATE OR REPLACE FUNCTION fetch_catalog_product_v1(p_country text, p_product_id text)
RETURNS jsonb
LANGUAGE plpgsql STABLE
AS $$
DECLARE
    prod catalog_it_products%ROWTYPE;
    ingredients JSONB;
    packages JSONB;
    atc_decoded JSONB;
    prevailing_class TEXT;
    shortages JSONB;
    has_shortage BOOLEAN;
BEGIN
    IF p_country <> 'it' THEN
        RETURN NULL;
    END IF;

    SELECT * INTO prod FROM catalog_it_products WHERE cod_farmaco = p_product_id;
    IF NOT FOUND THEN RETURN NULL; END IF;

    SELECT COALESCE(jsonb_agg(
        jsonb_build_object(
            'id', i.name || '-' || COALESCE(i.sort_order::text, '0'),
            'name', i.name,
            'strength_text', NULL
        ) ORDER BY i.sort_order
    ), '[]'::jsonb)
    INTO ingredients
    FROM catalog_it_ingredients i
    WHERE i.cod_farmaco = p_product_id;

    SELECT COALESCE(jsonb_agg(
        jsonb_build_object(
            'id', pkg.codice_aic,
            'source_package_id', pkg.codice_aic,
            'display_name', pkg.descrizione,
            'unit_count', pkg.unit_count,
            'package_type', pkg.package_type,
            'strength_text', pkg.strength_text,
            'requires_prescription', pkg.requires_prescription,
            'package_code', pkg.codice_aic,
            'fornitura_code', pkg.fornitura_code,
            'codice_atc', pkg.codice_atc,
            'forma', pkg.forma,
            'intake_method', pkg.intake_method,
            'reimbursement_class', pkg.reimbursement_class,
            'reference_price', pkg.reference_price,
            'reimbursement_note', pkg.reimbursement_note
        ) ORDER BY pkg.codice_aic
    ), '[]'::jsonb)
    INTO packages
    FROM catalog_it_packages pkg
    WHERE pkg.cod_farmaco = p_product_id
      AND pkg.stato_amministrativo = 'Autorizzata';

    atc_decoded := decode_atc(prod.codice_atc);

    SELECT class_value INTO prevailing_class FROM (
        SELECT reimbursement_class AS class_value, COUNT(*) AS cnt
        FROM catalog_it_packages
        WHERE cod_farmaco = p_product_id
          AND stato_amministrativo = 'Autorizzata'
          AND fornitura_code IN ('RR','RNR','RRL','RNRL','SOP','OTC','RMR')
          AND reimbursement_class IS NOT NULL
        GROUP BY reimbursement_class
        ORDER BY cnt DESC, class_value
        LIMIT 1
    ) sub;

    -- Carenze attive: stesso shape di fetch_shortages_for_product
    SELECT COALESCE(jsonb_agg(
        jsonb_build_object(
            'codice_aic', codice_aic,
            'reason', reason,
            'start_date', start_date,
            'expected_end_date', expected_end_date,
            'substitutes', substitutes
        ) ORDER BY start_date DESC NULLS LAST
    ), '[]'::jsonb)
    INTO shortages
    FROM catalog_it_shortages
    WHERE cod_farmaco = p_product_id AND resolved_at IS NULL;

    has_shortage := (jsonb_array_length(shortages) > 0);

    RETURN jsonb_build_object(
        'id', prod.id,
        'country', 'it',
        'source', 'aifa',
        'source_product_id', prod.cod_farmaco,
        'family_id', prod.cod_farmaco,
        'display_name', prod.denominazione,
        'brand_name', prod.denominazione,
        'generic_name', prod.pa_prevalente,
        'active_ingredients', ingredients,
        'dosage_form', prod.forma_prevalente,
        'routes', '[]'::jsonb,
        'strength_text', NULL,
        'manufacturer_name', prod.ragione_sociale,
        'requires_prescription', prod.requires_prescription,
        'availability', CASE WHEN prod.stato_amministrativo = 'Sospesa' THEN 'suspended' ELSE 'active' END,
        'atc_codes', COALESCE(to_jsonb(prod.codice_atc_all), '[]'::jsonb),
        'regulatory', jsonb_build_object(
            'tipo_procedura', prod.tipo_procedura,
            'is_homeopathic', prod.is_homeopathic,
            'fornitura_code', prod.fornitura_code
        ),
        'packages', packages,
        'source_meta', NULL,
        'link_fi', prod.link_fi,
        'link_rcp', prod.link_rcp,
        'fornitura_code', prod.fornitura_code,
        'codice_atc', prod.codice_atc,
        'atc_decoded', atc_decoded,
        'reimbursement_class', prevailing_class,
        'has_active_shortage', has_shortage,
        'shortages', shortages,
        'is_homeopathic', prod.is_homeopathic,
        'forme_distinte', COALESCE(to_jsonb(prod.forme_distinte), '[]'::jsonb)
    );
END;
$$;

COMMIT;
