-- ============================================================
-- Migration 011: Fix Supabase Security Advisor lints
-- ============================================================
-- Addresses issues reported by Supabase Database Linter:
--   ERROR: rls_disabled_in_public (3 catalog_it_* tables)
--   ERROR: security_definer_view (catalog_search_v1 + 3 stale US views)
--   WARN : function_search_path_mutable (3 functions)
--
-- Intentionally NOT addressed in this migration:
--   - auth_allow_anonymous_sign_ins: PharmaApp usa anonymous auth by design;
--     le policy restrittive sulle tabelle applicative filtrano già per auth.uid().
--   - extension_in_public (pg_trgm): spostare l'estensione rompe gli indici
--     gin_trgm_ops esistenti. Se serve, migrazione dedicata con rebuild indici.
--   - auth_leaked_password_protection: si attiva in Supabase Dashboard, non in SQL.
-- ============================================================


-- ============================================================
-- 1) RLS: catalog_it_products / catalog_it_packages / catalog_it_ingredients
-- ============================================================
-- I dati AIFA sono pubblici e read-only per il client.
-- Le scritture avvengono solo dall'import Python con service_role,
-- che BYPASSA RLS, quindi non servono policy di write.
-- ============================================================

ALTER TABLE public.catalog_it_products    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.catalog_it_packages    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.catalog_it_ingredients ENABLE ROW LEVEL SECURITY;

-- Drop di policy pre-esistenti (idempotenza)
DROP POLICY IF EXISTS catalog_it_products_read    ON public.catalog_it_products;
DROP POLICY IF EXISTS catalog_it_packages_read    ON public.catalog_it_packages;
DROP POLICY IF EXISTS catalog_it_ingredients_read ON public.catalog_it_ingredients;

CREATE POLICY catalog_it_products_read
    ON public.catalog_it_products
    FOR SELECT
    TO anon, authenticated
    USING (true);

CREATE POLICY catalog_it_packages_read
    ON public.catalog_it_packages
    FOR SELECT
    TO anon, authenticated
    USING (true);

CREATE POLICY catalog_it_ingredients_read
    ON public.catalog_it_ingredients
    FOR SELECT
    TO anon, authenticated
    USING (true);


-- ============================================================
-- 2) SECURITY DEFINER views
-- ============================================================
-- Droppiamo le 3 view US residue (non referenziate da nessuna parte del codice).
-- Ricreiamo catalog_search_v1 con security_invoker=true in modo che rispetti
-- le policy RLS dell'utente che interroga anziché quelle del creator.
-- ============================================================

DROP VIEW IF EXISTS public.catalog_us_search_v1          CASCADE;
DROP VIEW IF EXISTS public.catalog_us_product_detail_v1  CASCADE;
DROP VIEW IF EXISTS public.catalog_us_package_detail_v1  CASCADE;

-- Ricrea catalog_search_v1 con security_invoker (definizione copiata da 005)
DROP VIEW IF EXISTS public.catalog_search_v1 CASCADE;

CREATE VIEW public.catalog_search_v1
WITH (security_invoker = true) AS
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
    p.link_fi,
    p.link_rcp,
    pkg.fornitura_code,
    pkg.codice_atc,
    p.is_homeopathic
FROM public.catalog_it_packages pkg
JOIN public.catalog_it_products p ON p.cod_farmaco = pkg.cod_farmaco
WHERE pkg.stato_amministrativo = 'Autorizzata';

-- La view è letta in SELECT da client anon/authenticated
GRANT SELECT ON public.catalog_search_v1 TO anon, authenticated;


-- ============================================================
-- 3) function_search_path_mutable
-- ============================================================
-- Fissiamo un search_path esplicito per mitigare privilege escalation via
-- iniezione di oggetti in schemi nel path di ricerca.
-- ============================================================

ALTER FUNCTION public.update_updated_at()
    SET search_path = public, pg_temp;

ALTER FUNCTION public.fetch_catalog_package_v1(text, text)
    SET search_path = public, pg_temp;

ALTER FUNCTION public.fetch_catalog_product_v1(text, text)
    SET search_path = public, pg_temp;


-- ============================================================
-- NOTE OPERATIVE
-- ============================================================
-- Dopo l'applicazione:
--   1) Il backend FastAPI continua a funzionare (usa service_role → bypass RLS).
--   2) Il client iOS via PostgREST può leggere il catalogo ma non scriverlo.
--   3) Le nuove ricerche su catalog_search_v1 rispettano le policy RLS delle
--      tabelle sottostanti (che ora permettono SELECT a tutti).
--   4) Riesegui Supabase Advisor per confermare che i 7 ERROR e i 3 WARN
--      relativi a function_search_path_mutable siano risolti.
-- ============================================================
