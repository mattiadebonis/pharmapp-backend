-- =============================================================
-- Migration 048 — Drop dead schema (dead-code cleanup)
-- =============================================================
--
-- Rimuove oggetti DB risultati morti dall'analisi cross-layer
-- (verifica: 0 riferimenti né nel backend `app/`/`scripts/` né nel
-- data layer iOS, che parla con Supabase solo per l'auth — tutti i
-- dati passano da FastAPI `/v2/*`).
--
-- 3a) Funzioni / RPC / materialized view mai chiamate:
--   - is_caregiver_active_for(UUID)        — helper RLS mai adottato (mig 023)
--   - fetch_catalog_variants_v1(TEXT,TEXT) — RPC "per il futuro" mai esposta (mig 033)
--   - fetch_shortages_for_product(TEXT,TEXT)— shortage già inline in fetch_catalog_product_v1 (mig 035)
--   - audit_rule_examples(TEXT,INT)        — drill-down tooling mai cablato (mig 037)
--   - catalog_it_variants (MV) + refresh_catalog_variants() — MV mai interrogata;
--     search_catalog_products_v1 ricalcola al volo. NB: rimosso anche il blocco
--     di refresh in scripts/import_aifa_csv.py nello stesso commit.
--
-- 3b) Colonne vestigiali — assenti sia nella logica backend sia nel data
--     layer iOS; rimossi contestualmente i campi nei Pydantic DTO.
--   - doctors.schedule_json / secretary_schedule_json (mig 028, rimpiazzate da *_office_hours testo)
--   - medications.catalog_snapshot / image_url (mig 001, mai popolate/lette)
--   - profiles.parent_user_id (mig 001, design pre-caregiver; l'indice e la FK
--     vengono rimossi automaticamente col DROP COLUMN)
--
-- NON tocca: decode_atc (usata dentro fetch_catalog_product_v1),
--            audit.access_log, catalog_search_v1, catalog_it_packages_audit,
--            caregiver_relations.revoked_at (usata dalla policy RLS).
--
-- ⚠️ ORDINE DI DEPLOY (vincolante): applicare QUESTA MIGRATION **PRIMA** di
--    rilasciare il codice backend che rimuove i campi 3b dai Pydantic DTO.
--    Motivo: PharmaBaseModel usa `extra="forbid"`; finché le colonne esistono
--    nel DB, un `SELECT *` restituirebbe chiavi non più presenti nei DTO →
--    ValidationError (500) su /v2/bootstrap, /v2/doctors, ecc.
--    La migration è retro-compatibile col codice VECCHIO (i campi erano
--    Optional con default None), quindi la sequenza sicura è:
--       1) applicare 048  →  2) deployare il codice nuovo.
-- ⚠️ Applicare PRIMA su un branch/DB di staging, mai diretto in produzione.
-- =============================================================

BEGIN;

-- ---- 3a. Funzioni / RPC / materialized view ----------------

-- fetch_catalog_variants_v1 legge dalla MV catalog_it_variants → droppare prima la funzione
DROP FUNCTION IF EXISTS public.fetch_catalog_variants_v1(TEXT, TEXT);
DROP FUNCTION IF EXISTS public.refresh_catalog_variants();
DROP MATERIALIZED VIEW IF EXISTS public.catalog_it_variants CASCADE;

DROP FUNCTION IF EXISTS public.fetch_shortages_for_product(TEXT, TEXT);
DROP FUNCTION IF EXISTS public.audit_rule_examples(TEXT, INT);
DROP FUNCTION IF EXISTS public.is_caregiver_active_for(UUID);

-- ---- 3b. Colonne vestigiali --------------------------------

ALTER TABLE public.doctors      DROP COLUMN IF EXISTS schedule_json;
ALTER TABLE public.doctors      DROP COLUMN IF EXISTS secretary_schedule_json;
ALTER TABLE public.medications  DROP COLUMN IF EXISTS catalog_snapshot;
ALTER TABLE public.medications  DROP COLUMN IF EXISTS image_url;
ALTER TABLE public.profiles     DROP COLUMN IF EXISTS parent_user_id;

COMMIT;

-- =============================================================
-- Verifica post-apply (staging):
--   1. pytest app/tests/  → tutti verdi (DTO senza i campi rimossi)
--   2. GET /v2/bootstrap, /v2/doctors, medications, profiles → 200, nessun errore di serializzazione
--   3. scripts/import_aifa_csv.py → completa senza refresh di catalog_it_variants
--   4. Ricerca catalogo dall'app (search_catalog_products_v1 / fetch_catalog_product_v1) → invariata
-- =============================================================
