-- Minimal auth schema for local test stack.
-- Real Supabase ships this via GoTrue; for the docker-compose.test.yml
-- stack we recreate just enough so application migrations referencing
-- ``auth.users(id)`` can apply.

CREATE SCHEMA IF NOT EXISTS auth;

CREATE TABLE IF NOT EXISTS auth.users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email text UNIQUE,
    encrypted_password text,
    role text DEFAULT 'authenticated',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- Stub roles used by Supabase RLS / PostgREST. Real Supabase deploys
-- create these too; we add them so ``REVOKE ... FROM anon, authenticated``
-- in later migrations doesn't error.
DO $$ BEGIN
    CREATE ROLE anon NOLOGIN;
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE ROLE authenticated NOLOGIN;
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE ROLE service_role NOLOGIN BYPASSRLS;
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Stub auth.uid() / auth.jwt() helpers used by RLS policies.
-- PostgREST exposes the JWT either via the legacy single-claim setting
-- ``request.jwt.claim.sub`` or (since v10) the full claims JSON in
-- ``request.jwt.claims`` — read both for compatibility.
CREATE OR REPLACE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS $$
    SELECT NULLIF(
      coalesce(
        current_setting('request.jwt.claim.sub', true),
        (current_setting('request.jwt.claims', true)::jsonb ->> 'sub')
      ),
      ''
    )::uuid
$$;

CREATE OR REPLACE FUNCTION auth.jwt() RETURNS jsonb LANGUAGE sql STABLE AS $$
    SELECT COALESCE(current_setting('request.jwt.claims', true)::jsonb, '{}'::jsonb)
$$;

-- After all migrations apply (which REVOKE bulk grants), restore the
-- service_role's full access plus the default GRANTs Supabase deploys.
-- Real Supabase grants service_role on every new table by default; we
-- replicate that on the test stack. Authenticated/anon also get USAGE
-- on the auth schema so RLS-scoped queries can call ``auth.uid()``.
CREATE OR REPLACE FUNCTION auth._grant_service_role_all() RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    EXECUTE 'GRANT USAGE ON SCHEMA public TO service_role';
    EXECUTE 'GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO service_role';
    EXECUTE 'GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO service_role';
    EXECUTE 'GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO service_role';
    EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO service_role';

    EXECUTE 'GRANT USAGE ON SCHEMA auth TO anon, authenticated, service_role';
    EXECUTE 'GRANT EXECUTE ON FUNCTION auth.uid() TO anon, authenticated, service_role';
    EXECUTE 'GRANT EXECUTE ON FUNCTION auth.jwt() TO anon, authenticated, service_role';
    EXECUTE 'GRANT SELECT ON auth.users TO authenticated, service_role';
END $$;
