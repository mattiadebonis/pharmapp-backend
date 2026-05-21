-- =============================================================
-- Migration 032 — fetch_catalog_product_v1 espone atc_decoded
-- =============================================================
--
-- Nota storica: questa migration introduceva il campo `atc_decoded`
-- nel payload del prodotto (chiamando decode_atc dalla migration 031).
-- È stata successivamente RIMPIAZZATA dalla migration 034 (che aggiunge
-- reimbursement_class) e poi dalla 035 (che aggiunge shortages).
-- L'effetto netto sul DB attuale è dato dalla 035, l'ultima a fare
-- CREATE OR REPLACE FUNCTION fetch_catalog_product_v1.
--
-- Tieniamo il file per coerenza di numerazione e tracciabilità storia.
-- Il body è no-op se la funzione è già definita dalla 035: il
-- CREATE OR REPLACE qui sotto si limita ad aggiungere atc_decoded, ma
-- successive migration sovrascriveranno comunque. Idempotente.
-- =============================================================

CREATE OR REPLACE FUNCTION fetch_catalog_product_v1(p_country text, p_product_id text)
RETURNS jsonb
LANGUAGE plpgsql STABLE
AS $$
DECLARE
    prod catalog_it_products%ROWTYPE;
    ingredients JSONB;
    packages JSONB;
    atc_decoded JSONB;
BEGIN
    IF p_country <> 'it' THEN
        RETURN NULL;
    END IF;

    SELECT * INTO prod FROM catalog_it_products WHERE cod_farmaco = p_product_id;
    IF NOT FOUND THEN
        RETURN NULL;
    END IF;

    SELECT COALESCE(jsonb_agg(
        jsonb_build_object(
            'id', i.name || '-' || COALESCE(i.sort_order::text, '0'),
            'name', i.name,
            'strength_text', NULL
        ) ORDER BY i.sort_order
    ), '[]'::jsonb)
    INTO ingredients FROM catalog_it_ingredients i WHERE i.cod_farmaco = p_product_id;

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
    INTO packages FROM catalog_it_packages pkg
    WHERE pkg.cod_farmaco = p_product_id
      AND pkg.stato_amministrativo = 'Autorizzata';

    atc_decoded := decode_atc(prod.codice_atc);

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
        'is_homeopathic', prod.is_homeopathic,
        'forme_distinte', COALESCE(to_jsonb(prod.forme_distinte), '[]'::jsonb)
    );
END;
$$;
