-- =============================================================
-- Migration 034 — Classe di rimborsabilità AIFA
-- =============================================================
--
-- Contesto:
--   AIFA classifica ogni AIC secondo la "fascia" di rimborsabilità:
--     - A      → rimborsato dal SSN (essenziale)
--     - A-PHT  → rimborsato A, distribuzione PHT (specifica)
--     - H      → uso ospedaliero, rimborsato SSN solo se erogato in
--                ospedale
--     - C      → non rimborsato (a carico del paziente)
--     - C-bis  → non rimborsato, lista "fascia C bis" (OTC con
--                accise particolari)
--     - Cnn    → classe negoziale "non negoziata" (transitoria,
--                rimborsato per default ma in attesa di negoziato
--                prezzo)
--
--   Le liste di trasparenza sono pubblicate da AIFA come Excel
--   mensile sul portale "liste-farmaci-a-h":
--     https://www.aifa.gov.it/liste-farmaci-a-h
--
--   Dati esposti nel CSV/XLSX: codice AIC, classe, prezzo di
--   riferimento, eventuale nota AIFA.
--
--   Aggiungiamo qui i campi a catalog_it_packages e aggiorniamo
--   l'RPC fetch_catalog_product_v1/fetch_catalog_package_v1 per
--   esporli. L'importer è in scripts/import_aifa_trasparenza.py.
--
--   I campi sono NULLABLE: senza l'import iniziale tutto è NULL,
--   il client deve gestire l'assenza con "—" o "Da verificare".
-- =============================================================

BEGIN;

-- ─── Schema: nuovi campi su catalog_it_packages ──────────────────
ALTER TABLE catalog_it_packages
    ADD COLUMN IF NOT EXISTS reimbursement_class TEXT,
    ADD COLUMN IF NOT EXISTS reference_price NUMERIC(10, 4),
    ADD COLUMN IF NOT EXISTS reimbursement_note TEXT,
    ADD COLUMN IF NOT EXISTS reimbursement_updated_at TIMESTAMPTZ;

-- Vincolo: classe deve essere uno dei valori AIFA noti (o NULL)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'catalog_it_packages_reimbursement_class_chk'
    ) THEN
        ALTER TABLE catalog_it_packages
            ADD CONSTRAINT catalog_it_packages_reimbursement_class_chk
            CHECK (reimbursement_class IS NULL OR reimbursement_class IN (
                'A', 'A-PHT', 'H', 'C', 'C-bis', 'Cnn'
            ));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_catalog_it_packages_reimbursement_class
    ON catalog_it_packages (reimbursement_class)
    WHERE reimbursement_class IS NOT NULL;

COMMENT ON COLUMN catalog_it_packages.reimbursement_class IS
    'Classe AIFA: A=SSN-rimborsato, H=ospedaliero, C=a carico paziente, '
    'A-PHT=PHT, C-bis=fascia C bis, Cnn=non negoziata. NULL se non ancora '
    'importato dalle liste di trasparenza. Migration 034.';

COMMENT ON COLUMN catalog_it_packages.reference_price IS
    'Prezzo di riferimento AIFA in EUR (dalla lista di trasparenza). '
    'Per classe A è il prezzo rimborsato dal SSN. Migration 034.';

COMMENT ON COLUMN catalog_it_packages.reimbursement_note IS
    'Note AIFA sulla rimborsabilità (es. "Nota 13", "Piano terapeutico"). '
    'Migration 034.';

COMMENT ON COLUMN catalog_it_packages.reimbursement_updated_at IS
    'Quando lo script di import_aifa_trasparenza ha aggiornato '
    'l''ultima volta il dato. Migration 034.';


-- ─── Aggiornamento RPC fetch_catalog_product_v1 ──────────────────
--
-- Aggiungiamo ai pacchetti tre nuovi campi e calcoliamo a livello
-- product un summary: "prevailing_reimbursement_class" = la classe
-- più frequente fra i package autorizzati pubblici (la maggior
-- parte dei farmaci ha la stessa classe per tutte le confezioni,
-- ma per alcuni multi-formato c'è variazione minore).
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

    -- Prevailing reimbursement_class: il valore più frequente fra i
    -- package pubblici autorizzati. NULL se nessuna confezione ha
    -- ancora reimbursement_class popolato.
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
        'is_homeopathic', prod.is_homeopathic,
        'forme_distinte', COALESCE(to_jsonb(prod.forme_distinte), '[]'::jsonb)
    );
END;
$$;


-- ─── Aggiornamento RPC fetch_catalog_package_v1 ──────────────────
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
        'reimbursement_class', pkg.reimbursement_class,
        'reimbursement_text', pkg.reimbursement_note,
        'reference_price', pkg.reference_price,
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

COMMIT;
