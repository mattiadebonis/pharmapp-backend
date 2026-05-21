-- =============================================================
-- Migration 033 — catalog_it_variants (MATERIALIZED VIEW)
-- =============================================================
--
-- Contesto:
--   Oggi l'iOS calcola le "varianti cliniche" (cod_farmaco × strength
--   × forma) lato client in `MedicationSetupView.groupVariants()`,
--   dopo aver scaricato TUTTE le confezioni del prodotto e
--   raggruppato in memoria. Lo stesso raggruppamento esiste anche
--   server-side dentro `search_catalog_products_v1` (COUNT DISTINCT)
--   ma ricomputato a ogni search.
--
--   Introduciamo una MATERIALIZED VIEW pre-aggregata sui packages
--   pubblici autorizzati. Benefici:
--     - Una sola fonte di verità per "cos'è una variante"
--     - Query SQL diretta (no GROUP BY runtime su 150k+ righe)
--     - Aggregati utili pre-calcolati (n. confezioni per variante,
--       range unit_count, lista AIC ordinata, fornitura prevalente)
--     - Possibilità futura di esporre un endpoint
--       /catalog/variants pulito per nuove UI
--
--   Refresh: chiamare `refresh_catalog_variants()` al termine
--   dell'import CSV. CONCURRENTLY → niente lock in lettura
--   (richiede l'unique index sotto).
--
--   Filtraggio: stato_amministrativo = 'Autorizzata' AND fornitura
--   pubblica. Stesso filtro applicato in catalog_search_v1 → la
--   view rispecchia ESATTAMENTE ciò che l'app può mostrare.
-- =============================================================

BEGIN;

-- ─── Materialized view ───────────────────────────────────────────
DROP MATERIALIZED VIEW IF EXISTS catalog_it_variants CASCADE;

CREATE MATERIALIZED VIEW catalog_it_variants AS
SELECT
    -- Chiave variante: cod_farmaco|strength_text|forma. NULL diventano
    -- stringa vuota per coerenza (Postgres GROUP BY tratta NULL come
    -- gruppo a sé, ma in chiave concatenata vogliamo deterministico).
    pkg.cod_farmaco
        || '|' || COALESCE(pkg.strength_text, '')
        || '|' || COALESCE(pkg.forma, '')
        AS variant_key,
    pkg.cod_farmaco,
    pkg.strength_text,
    pkg.strength_value,
    pkg.strength_unit,
    pkg.forma,
    pkg.intake_method,
    -- Aggregati confezioni
    COUNT(*)::int AS package_count,
    BOOL_OR(pkg.requires_prescription) AS requires_prescription,
    MIN(pkg.unit_count)::int AS min_unit_count,
    MAX(pkg.unit_count)::int AS max_unit_count,
    -- Lista AIC ordinata per unit_count (utile a UI per
    -- "blister da 14, da 28, da 30..." in ordine ascendente)
    ARRAY_AGG(pkg.codice_aic ORDER BY pkg.unit_count NULLS LAST, pkg.codice_aic) AS package_aics,
    -- Fornitura: lista deduped + il valore più frequente (per il
    -- caso normale dove tutta la variante condivide la stessa).
    ARRAY_AGG(DISTINCT pkg.fornitura_code) FILTER (WHERE pkg.fornitura_code IS NOT NULL) AS fornitura_codes,
    -- Volume: presenti solo per liquidi/topici. Min/max per
    -- distinguere "tubo 30g" da "tubo 100g" della stessa variante.
    MIN(pkg.volume_value) AS min_volume_value,
    MAX(pkg.volume_value) AS max_volume_value,
    MIN(pkg.volume_unit) AS volume_unit_min,
    -- ATC associato (dovrebbe essere lo stesso per tutta la variante)
    MIN(pkg.codice_atc) AS codice_atc
FROM catalog_it_packages pkg
WHERE pkg.stato_amministrativo = 'Autorizzata'
  -- Stesso filtro pubblico di catalog_search_v1 (migration 015)
  AND pkg.fornitura_code IN ('RR','RNR','RRL','RNRL','SOP','OTC','RMR')
GROUP BY
    pkg.cod_farmaco,
    pkg.strength_text,
    pkg.strength_value,
    pkg.strength_unit,
    pkg.forma,
    pkg.intake_method
WITH DATA;

COMMENT ON MATERIALIZED VIEW catalog_it_variants IS
    'Aggregazione varianti cliniche (cod_farmaco x strength x forma) '
    'sui packages pubblici autorizzati. Migration 033. Refresh via '
    'refresh_catalog_variants() — chiamare dopo ogni import AIFA.';

-- Indici (UNIQUE per CONCURRENTLY refresh, gli altri per lookup)
CREATE UNIQUE INDEX idx_catalog_it_variants_key
    ON catalog_it_variants (variant_key);
CREATE INDEX idx_catalog_it_variants_product
    ON catalog_it_variants (cod_farmaco);
CREATE INDEX idx_catalog_it_variants_atc
    ON catalog_it_variants (codice_atc);


-- ─── Funzione di refresh ─────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.refresh_catalog_variants()
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY catalog_it_variants;
END;
$$;

COMMENT ON FUNCTION public.refresh_catalog_variants IS
    'Refresh CONCURRENTLY della view catalog_it_variants. Chiamato '
    'al termine di scripts/import_aifa_csv.py dopo l''upsert dei '
    'packages. Migration 033.';

-- Solo service-role può fare refresh (è un''operazione di import).
-- authenticated/anon esclusi: il refresh è una operazione amministrativa,
-- non un endpoint per i client.
REVOKE EXECUTE ON FUNCTION public.refresh_catalog_variants FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.refresh_catalog_variants TO service_role;


-- ─── RPC pubblica: fetch varianti per prodotto ───────────────────
--
-- Restituisce un array JSON ordinato per dosaggio crescente. Pensata
-- per sostituire (in futuro) la chiamata fetchCatalogProductDetail
-- → groupVariants() lato iOS, dando direttamente l'array varianti
-- senza scaricare l'elenco completo dei packages.
CREATE OR REPLACE FUNCTION public.fetch_catalog_variants_v1(
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
            'variant_key', variant_key,
            'cod_farmaco', cod_farmaco,
            'strength_text', strength_text,
            'strength_value', strength_value,
            'strength_unit', strength_unit,
            'forma', forma,
            'intake_method', intake_method,
            'package_count', package_count,
            'requires_prescription', requires_prescription,
            'min_unit_count', min_unit_count,
            'max_unit_count', max_unit_count,
            'package_aics', to_jsonb(package_aics),
            'fornitura_codes', to_jsonb(fornitura_codes),
            'min_volume_value', min_volume_value,
            'max_volume_value', max_volume_value,
            'volume_unit', volume_unit_min,
            'codice_atc', codice_atc
        )
        -- Ordinamento clinico: dosaggio crescente. NULL in coda.
        ORDER BY strength_value NULLS LAST, strength_text, forma
    ), '[]'::jsonb)
    INTO result
    FROM catalog_it_variants
    WHERE cod_farmaco = p_product_id;

    RETURN result;
END;
$$;

GRANT EXECUTE ON FUNCTION public.fetch_catalog_variants_v1(TEXT, TEXT) TO authenticated;


-- ─── Grants ──────────────────────────────────────────────────────
-- La view è leggibile da authenticated (stesso scope di
-- catalog_search_v1). anon esclusa per coerenza con migration 012.
GRANT SELECT ON catalog_it_variants TO authenticated;
REVOKE ALL ON catalog_it_variants FROM PUBLIC, anon;

COMMIT;
