-- =============================================================
-- Migration 013 — Catalogo: Title Case + solo confezioni al pubblico
-- =============================================================
-- Contesto:
--   1. La view `catalog_search_v1` e le RPC `fetch_catalog_*_v1` restituiscono
--      i nomi AIFA in ALL CAPS (es. "RAMIPRIL SANDOZ"). UX vuole Title Case
--      ("Ramipril Sandoz"). Usiamo `initcap()` built-in: capitalizza la prima
--      lettera di ogni parola, mantenendo il resto in lowercase.
--   2. La ricerca espone pure farmaci a uso esclusivo ospedaliero o
--      specialistico (fornitura_code = 'OSP' / 'USPL' / 'ND'). Questi non
--      sono acquistabili in farmacia al pubblico. Escludiamo dalla view +
--      dai packages restituiti dalla RPC product.
--   Forniture MANTENUTE (vendibili in farmacia al pubblico):
--     RR    - ricetta ripetibile
--     RNR   - ricetta non ripetibile
--     RRL   - ricetta limitativa (specialisti)
--     RNRL  - ricetta non ripetibile limitativa
--     SOP   - non soggetti a prescrizione ma non da banco
--     OTC   - da banco
--     RMR   - ricetta ministeriale (stupefacenti) — comunque vendibile
--   Forniture ESCLUSE:
--     OSP   - esclusivo ospedaliero
--     USPL  - esclusivo specialista
--     ND    - non definito / vuoto
-- =============================================================

BEGIN;

-- 1) View
DROP VIEW IF EXISTS public.catalog_search_v1 CASCADE;

CREATE VIEW public.catalog_search_v1
WITH (security_invoker = true) AS
SELECT
    'it'::text AS country,
    'aifa'::text AS source,
    p.cod_farmaco AS product_id,
    pkg.codice_aic AS package_id,
    p.cod_farmaco AS family_id,
    initcap(pkg.denominazione) AS display_name,
    initcap(pkg.denominazione) AS brand_name,
    initcap(pkg.pa_associati)  AS generic_name,
    initcap(pkg.pa_associati)  AS principle,
    pkg.requires_prescription,
    pkg.descrizione AS package_label,
    COALESCE(pkg.unit_count, 1) AS units_per_package,
    pkg.forma AS form_type,
    COALESCE(pkg.strength_value, 0)::int AS dosage_value,
    COALESCE(pkg.strength_unit, '') AS dosage_unit,
    COALESCE(
        CASE WHEN pkg.volume_value IS NOT NULL
             THEN pkg.volume_value::text || ' ' || COALESCE(pkg.volume_unit, '')
             ELSE '' END,
        ''
    ) AS volume,
    CASE WHEN pkg.stato_amministrativo = 'Sospesa' THEN 'suspended' ELSE 'active' END AS availability,
    pkg.codice_aic AS catalog_code,
    '{}'::jsonb AS catalog_snapshot,
    p.link_fi,
    p.link_rcp,
    pkg.fornitura_code,
    pkg.codice_atc,
    p.is_homeopathic
FROM public.catalog_it_packages pkg
JOIN public.catalog_it_products p ON p.cod_farmaco = pkg.cod_farmaco
WHERE pkg.stato_amministrativo = 'Autorizzata'
  AND pkg.fornitura_code IN ('RR','RNR','RRL','RNRL','SOP','OTC','RMR');

REVOKE ALL ON public.catalog_search_v1 FROM PUBLIC, anon;
GRANT SELECT ON public.catalog_search_v1 TO authenticated;


-- 2) RPC fetch_catalog_product_v1 — Title Case + filtra packages al pubblico
CREATE OR REPLACE FUNCTION fetch_catalog_product_v1(p_country text, p_product_id text)
RETURNS jsonb
LANGUAGE plpgsql STABLE
SET search_path = public, pg_temp
AS $$
DECLARE
    prod catalog_it_products%ROWTYPE;
    ingredients JSONB;
    packages JSONB;
BEGIN
    IF p_country <> 'it' THEN
        RETURN NULL;
    END IF;

    SELECT * INTO prod
    FROM catalog_it_products
    WHERE cod_farmaco = p_product_id;

    IF NOT FOUND THEN
        RETURN NULL;
    END IF;

    SELECT COALESCE(jsonb_agg(
        jsonb_build_object(
            'id', i.name || '-' || COALESCE(i.sort_order::text, '0'),
            'name', initcap(i.name),
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
            'intake_method', pkg.intake_method
        ) ORDER BY pkg.codice_aic
    ), '[]'::jsonb)
    INTO packages
    FROM catalog_it_packages pkg
    WHERE pkg.cod_farmaco = p_product_id
      AND pkg.stato_amministrativo = 'Autorizzata'
      AND pkg.fornitura_code IN ('RR','RNR','RRL','RNRL','SOP','OTC','RMR');

    RETURN jsonb_build_object(
        'id', prod.id,
        'country', 'it',
        'source', 'aifa',
        'source_product_id', prod.cod_farmaco,
        'family_id', prod.cod_farmaco,
        'display_name', initcap(prod.denominazione),
        'brand_name', initcap(prod.denominazione),
        'generic_name', initcap(prod.pa_prevalente),
        'active_ingredients', ingredients,
        'dosage_form', prod.forma_prevalente,
        'routes', '[]'::jsonb,
        'strength_text', NULL,
        'manufacturer_name', initcap(prod.ragione_sociale),
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
        'is_homeopathic', prod.is_homeopathic,
        'forme_distinte', COALESCE(to_jsonb(prod.forme_distinte), '[]'::jsonb)
    );
END;
$$;


-- 3) RPC fetch_catalog_package_v1 — solo se la confezione è al pubblico
CREATE OR REPLACE FUNCTION fetch_catalog_package_v1(p_country text, p_package_id text)
RETURNS jsonb
LANGUAGE plpgsql STABLE
SET search_path = public, pg_temp
AS $$
DECLARE
    pkg catalog_it_packages%ROWTYPE;
BEGIN
    IF p_country <> 'it' THEN
        RETURN NULL;
    END IF;

    SELECT * INTO pkg
    FROM catalog_it_packages
    WHERE codice_aic = p_package_id
      AND fornitura_code IN ('RR','RNR','RRL','RNRL','SOP','OTC','RMR');

    IF NOT FOUND THEN
        RETURN NULL;
    END IF;

    RETURN jsonb_build_object(
        'id', pkg.id,
        'source_package_id', pkg.codice_aic,
        'package_code', pkg.codice_aic,
        'display_name', pkg.descrizione,
        'unit_count', pkg.unit_count,
        'package_type', pkg.package_type,
        'volume_value', pkg.volume_value,
        'volume_unit', pkg.volume_unit,
        'strength_text', pkg.strength_text,
        'marketed', true,
        'marketing_start_date', NULL,
        'marketing_end_date', NULL,
        'is_sample', false,
        'requires_prescription', pkg.requires_prescription,
        'reimbursement_class', NULL,
        'reimbursement_text', NULL,
        'shortage_reason', NULL,
        'shortage_start_date', NULL,
        'shortage_end_date', NULL,
        'availability', CASE WHEN pkg.stato_amministrativo = 'Sospesa' THEN 'suspended' ELSE 'active' END,
        'source_meta', NULL,
        'fornitura', pkg.fornitura,
        'fornitura_code', pkg.fornitura_code,
        'codice_atc', pkg.codice_atc,
        'forma', pkg.forma,
        'intake_method', pkg.intake_method
    );
END;
$$;

-- EXECUTE rights
REVOKE EXECUTE ON FUNCTION public.fetch_catalog_product_v1(text, text) FROM PUBLIC, anon;
REVOKE EXECUTE ON FUNCTION public.fetch_catalog_package_v1(text, text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.fetch_catalog_product_v1(text, text) TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.fetch_catalog_package_v1(text, text) TO authenticated, service_role;

COMMIT;
