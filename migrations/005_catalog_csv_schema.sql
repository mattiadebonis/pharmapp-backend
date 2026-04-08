-- ============================================================
-- Migration 005: Catalog AIFA from CSV (confezioni_fornitura)
-- Replaces ad-hoc catalog_it_raw_* tables with formal schema
-- ============================================================

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ============================================================
-- DROP OLD TABLES (created by import_aifa.py, not in migrations)
-- ============================================================
DROP VIEW IF EXISTS catalog_search_v1 CASCADE;
DROP FUNCTION IF EXISTS fetch_catalog_product_v1(TEXT, TEXT) CASCADE;
DROP FUNCTION IF EXISTS fetch_catalog_package_v1(TEXT, TEXT) CASCADE;
DROP TABLE IF EXISTS catalog_it_raw_ingredients CASCADE;
DROP TABLE IF EXISTS catalog_it_raw_packages CASCADE;
DROP TABLE IF EXISTS catalog_it_raw_products CASCADE;

-- ============================================================
-- HELPER FUNCTION (if not already created by earlier migrations)
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- CATALOG_IT_PRODUCTS (1 row per COD_FARMACO)
-- ============================================================
CREATE TABLE catalog_it_products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cod_farmaco TEXT UNIQUE NOT NULL,
    denominazione TEXT NOT NULL,
    codice_ditta INTEGER,
    ragione_sociale TEXT,
    codice_atc TEXT,
    codice_atc_all TEXT[] DEFAULT '{}',
    tipo_procedura TEXT,
    is_homeopathic BOOLEAN NOT NULL DEFAULT false,
    requires_prescription BOOLEAN NOT NULL DEFAULT false,
    fornitura_code TEXT,
    stato_amministrativo TEXT,
    forma_prevalente TEXT,
    forme_distinte TEXT[] DEFAULT '{}',
    pa_prevalente TEXT,
    link_fi TEXT,
    link_rcp TEXT,
    source TEXT NOT NULL DEFAULT 'aifa',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_cat_prod_codice_atc ON catalog_it_products(codice_atc);
CREATE INDEX idx_cat_prod_is_homeopathic ON catalog_it_products(is_homeopathic);
CREATE INDEX idx_cat_prod_denominazione_trgm ON catalog_it_products
    USING gin (denominazione gin_trgm_ops);

-- ============================================================
-- CATALOG_IT_PACKAGES (1 row per CODICE_AIC, ~159K rows)
-- ============================================================
CREATE TABLE catalog_it_packages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    codice_aic TEXT UNIQUE NOT NULL,
    cod_farmaco TEXT NOT NULL REFERENCES catalog_it_products(cod_farmaco) ON DELETE CASCADE,
    cod_confezione TEXT,
    denominazione TEXT NOT NULL,
    descrizione TEXT,
    forma TEXT,
    codice_atc TEXT,
    pa_associati TEXT,
    stato_amministrativo TEXT,
    tipo_procedura TEXT,
    fornitura TEXT,
    fornitura_code TEXT,
    requires_prescription BOOLEAN NOT NULL DEFAULT false,
    -- Parsed from DESCRIZIONE
    unit_count INTEGER DEFAULT 1,
    package_type TEXT,
    strength_value FLOAT,
    strength_unit TEXT,
    strength_text TEXT,
    volume_value FLOAT,
    volume_unit TEXT,
    -- Metadata
    source TEXT NOT NULL DEFAULT 'aifa',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Trigram indexes for ILIKE search
CREATE INDEX idx_cat_pkg_denominazione_trgm ON catalog_it_packages
    USING gin (denominazione gin_trgm_ops);
CREATE INDEX idx_cat_pkg_pa_trgm ON catalog_it_packages
    USING gin (pa_associati gin_trgm_ops);
CREATE INDEX idx_cat_pkg_descrizione_trgm ON catalog_it_packages
    USING gin (descrizione gin_trgm_ops);

-- Lookup indexes
CREATE INDEX idx_cat_pkg_cod_farmaco ON catalog_it_packages(cod_farmaco);
CREATE INDEX idx_cat_pkg_codice_atc ON catalog_it_packages(codice_atc);
CREATE INDEX idx_cat_pkg_fornitura_code ON catalog_it_packages(fornitura_code);
CREATE INDEX idx_cat_pkg_stato ON catalog_it_packages(stato_amministrativo);

-- ============================================================
-- CATALOG_IT_INGREDIENTS (split from PA_ASSOCIATI)
-- ============================================================
CREATE TABLE catalog_it_ingredients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cod_farmaco TEXT NOT NULL REFERENCES catalog_it_products(cod_farmaco) ON DELETE CASCADE,
    name TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    UNIQUE(cod_farmaco, name)
);

CREATE INDEX idx_cat_ingredients_cod ON catalog_it_ingredients(cod_farmaco);
CREATE INDEX idx_cat_ingredients_name_trgm ON catalog_it_ingredients
    USING gin (name gin_trgm_ops);

-- ============================================================
-- UPDATED_AT TRIGGERS
-- ============================================================
CREATE TRIGGER catalog_it_products_updated_at
    BEFORE UPDATE ON catalog_it_products
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER catalog_it_packages_updated_at
    BEFORE UPDATE ON catalog_it_packages
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================
-- SEARCH VIEW (compatible with existing catalog_service.py)
-- ============================================================
CREATE OR REPLACE VIEW catalog_search_v1 AS
SELECT
    'it'::text AS country,
    'aifa'::text AS source,
    p.cod_farmaco AS product_id,
    pkg.codice_aic AS package_id,
    p.cod_farmaco AS family_id,
    pkg.denominazione AS display_name,
    pkg.denominazione AS brand_name,
    pkg.pa_associati AS generic_name,
    pkg.pa_associati AS principle,
    pkg.requires_prescription,
    pkg.descrizione AS package_label,
    COALESCE(pkg.unit_count, 1) AS units,
    pkg.forma AS tipologia,
    COALESCE(pkg.strength_value, 0)::int AS valore,
    COALESCE(pkg.strength_unit, '') AS unita,
    COALESCE(
        CASE WHEN pkg.volume_value IS NOT NULL
             THEN pkg.volume_value::text || ' ' || COALESCE(pkg.volume_unit, '')
             ELSE '' END,
        ''
    ) AS volume,
    CASE WHEN pkg.stato_amministrativo = 'Sospesa' THEN 'suspended' ELSE 'active' END AS availability,
    pkg.codice_aic AS catalog_code,
    -- New fields
    p.link_fi,
    p.link_rcp,
    pkg.fornitura_code,
    pkg.codice_atc,
    p.is_homeopathic
FROM catalog_it_packages pkg
JOIN catalog_it_products p ON p.cod_farmaco = pkg.cod_farmaco
WHERE pkg.stato_amministrativo = 'Autorizzata';

-- ============================================================
-- RPC: fetch_catalog_product_v1(country, product_id)
-- Returns JSON matching CatalogProductDTO shape
-- ============================================================
CREATE OR REPLACE FUNCTION fetch_catalog_product_v1(
    p_country TEXT,
    p_product_id TEXT
) RETURNS JSONB AS $$
DECLARE
    prod catalog_it_products%ROWTYPE;
    ingredients JSONB;
    packages JSONB;
BEGIN
    -- Only Italian catalog supported
    IF p_country <> 'it' THEN
        RETURN NULL;
    END IF;

    SELECT * INTO prod
    FROM catalog_it_products
    WHERE cod_farmaco = p_product_id;

    IF NOT FOUND THEN
        RETURN NULL;
    END IF;

    -- Build ingredients array
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

    -- Build packages array
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
            'forma', pkg.forma
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
$$ LANGUAGE plpgsql STABLE;

-- ============================================================
-- RPC: fetch_catalog_package_v1(country, package_id)
-- Returns JSON matching CatalogPackageDTO shape
-- ============================================================
CREATE OR REPLACE FUNCTION fetch_catalog_package_v1(
    p_country TEXT,
    p_package_id TEXT
) RETURNS JSONB AS $$
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
        'forma', pkg.forma
    );
END;
$$ LANGUAGE plpgsql STABLE;
