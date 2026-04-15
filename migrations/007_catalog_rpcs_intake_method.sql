-- Update RPC functions to include intake_method field

CREATE OR REPLACE FUNCTION fetch_catalog_package_v1(p_country text, p_package_id text)
RETURNS jsonb
LANGUAGE plpgsql STABLE
AS $$
DECLARE
    pkg catalog_it_packages%ROWTYPE;
BEGIN
    IF p_country <> 'it' THEN
        RETURN NULL;
    END IF;

    SELECT * INTO pkg
    FROM catalog_it_packages
    WHERE codice_aic = p_package_id;

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

CREATE OR REPLACE FUNCTION fetch_catalog_product_v1(p_country text, p_product_id text)
RETURNS jsonb
LANGUAGE plpgsql STABLE
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
            'intake_method', pkg.intake_method
        ) ORDER BY pkg.codice_aic
    ), '[]'::jsonb)
    INTO packages
    FROM catalog_it_packages pkg
    WHERE pkg.cod_farmaco = p_product_id
      AND pkg.stato_amministrativo = 'Autorizzata';

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
        'is_homeopathic', prod.is_homeopathic,
        'forme_distinte', COALESCE(to_jsonb(prod.forme_distinte), '[]'::jsonb)
    );
END;
$$;
