-- =============================================================
-- Migration 012 — Catalogo leggibile SOLO da ruolo `authenticated`
-- =============================================================
-- Contesto:
--   Le policy della migration 011 aprivano le tabelle catalog_it_* anche al
--   ruolo `anon` (USING (true) FOR SELECT TO anon, authenticated). Questo
--   permetteva a chiunque avesse solo l'anon key Supabase — senza aver
--   eseguito nemmeno il `signInAnonymously` — di leggere l'intero catalogo
--   farmaci. Vulnerabilità: la tabella diventa de-facto pubblica ed è
--   scrapable. La app iOS però autentica sempre l'utente (anche quando è
--   un utente anonimo, via `supabase.auth.signInAnonymously()`), quindi la
--   sessione porta un JWT con `role: authenticated`.
--
-- Obiettivo:
--   1. Tabelle catalog_it_products / catalog_it_packages / catalog_it_ingredients
--      leggibili solo da `authenticated` (copre utenti reali E utenti
--      autenticati anonimamente).
--   2. Role `anon` (senza sessione) NON può leggere.
--   3. Service role (backend FastAPI) continua a bypassare RLS.
--   4. View `catalog_search_v1` e RPC `fetch_catalog_*_v1` vengono allineate.
-- =============================================================

BEGIN;

-- 1) Policy: ricreate senza `anon`
DROP POLICY IF EXISTS catalog_it_products_read    ON public.catalog_it_products;
DROP POLICY IF EXISTS catalog_it_packages_read    ON public.catalog_it_packages;
DROP POLICY IF EXISTS catalog_it_ingredients_read ON public.catalog_it_ingredients;

CREATE POLICY catalog_it_products_read
    ON public.catalog_it_products
    FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY catalog_it_packages_read
    ON public.catalog_it_packages
    FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY catalog_it_ingredients_read
    ON public.catalog_it_ingredients
    FOR SELECT
    TO authenticated
    USING (true);


-- 2) Table grants: revoca tutto da `anon` sulle tabelle catalogo.
--    Nota: revochiamo TUTTI i privilegi perché il default GRANTS di Supabase
--    include INSERT/UPDATE/DELETE anche per `anon` — non solo SELECT.
--    Su `authenticated` lasciamo il solo SELECT (no write dal client).
REVOKE ALL ON public.catalog_it_products    FROM anon;
REVOKE ALL ON public.catalog_it_packages    FROM anon;
REVOKE ALL ON public.catalog_it_ingredients FROM anon;

REVOKE ALL ON public.catalog_it_products    FROM authenticated;
REVOKE ALL ON public.catalog_it_packages    FROM authenticated;
REVOKE ALL ON public.catalog_it_ingredients FROM authenticated;

GRANT SELECT ON public.catalog_it_products    TO authenticated;
GRANT SELECT ON public.catalog_it_packages    TO authenticated;
GRANT SELECT ON public.catalog_it_ingredients TO authenticated;


-- 3) View: stessa politica — solo authenticated
REVOKE ALL ON public.catalog_search_v1 FROM anon;
REVOKE ALL ON public.catalog_search_v1 FROM authenticated;
GRANT SELECT ON public.catalog_search_v1 TO authenticated;


-- 4) RPC: revoca EXECUTE sia dal ruolo `anon` sia dal PUBLIC (le funzioni in
--    Postgres hanno di default EXECUTE a PUBLIC — non basta revocare `anon`,
--    perché `anon` eredita tramite PUBLIC). Poi ri-grant mirato ai ruoli
--    legittimi. Questo chiude l'accesso anonymous-key-only alle RPC.
REVOKE EXECUTE ON FUNCTION public.fetch_catalog_product_v1(text, text) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.fetch_catalog_package_v1(text, text) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.fetch_catalog_product_v1(text, text) FROM anon;
REVOKE EXECUTE ON FUNCTION public.fetch_catalog_package_v1(text, text) FROM anon;

GRANT EXECUTE ON FUNCTION public.fetch_catalog_product_v1(text, text) TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.fetch_catalog_package_v1(text, text) TO authenticated, service_role;

COMMIT;

-- =============================================================
-- Verifica post-apply:
--   SELECT roles FROM pg_policies WHERE tablename LIKE 'catalog_it_%';
--     → atteso {authenticated} (no anon)
--   SELECT grantee FROM information_schema.role_table_grants
--     WHERE table_name IN ('catalog_it_products','catalog_it_packages',
--                          'catalog_it_ingredients','catalog_search_v1');
--     → per `anon` 0 righe; per `authenticated` solo SELECT.
-- =============================================================
