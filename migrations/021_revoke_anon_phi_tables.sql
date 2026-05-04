-- =============================================================
-- Migration 021 — Defense in depth: REVOKE anon + minimal grants on PHI
-- =============================================================
-- Contesto:
--   Le migration 011 e 012 hanno già messo in sicurezza il catalogo. Le
--   tabelle PHI (Protected Health Information) operative dell'app hanno
--   tutte RLS abilitata con policy che filtrano per `auth.uid()`, ma:
--     - Supabase di default GRANTa SELECT/INSERT/UPDATE/DELETE al ruolo
--       `anon` su qualunque tabella in `public`.
--     - Se in futuro una migration disabilitasse inavvertitamente RLS, il
--       client con sola anon-key potrebbe leggere/scrivere PHI.
--   Defense in depth: revochiamo tutto da `anon`, lasciando il diritto
--   solo al ruolo `authenticated` (e service_role bypassa RLS).
--
-- Obiettivo:
--   1. `anon` non ha NESSUN privilegio sulle tabelle PHI.
--   2. `authenticated` ha SELECT/INSERT/UPDATE/DELETE espliciti, mediati
--      sempre dalle policy RLS (che filtrano per auth.uid()).
--   3. service_role: continua a bypassare RLS (backend FastAPI).
-- =============================================================

BEGIN;

-- Tabelle PHI: dati sanitari + dati personali utente
-- (Catalogo AIFA è già hardenato in 012; qui copriamo solo le tabelle utente.)
DO $$
DECLARE
    t TEXT;
    phi_tables TEXT[] := ARRAY[
        'profiles',
        'medications',
        'dosing_schedules',
        'supplies',
        'prescriptions',
        'prescription_requests',
        'doctors',
        'dose_events',
        'routines',
        'routine_steps',
        'parameters',
        'measurements',
        'caregiver_relations',
        'pending_changes',
        'activity_logs',
        'device_tokens',
        'user_settings'
    ];
BEGIN
    FOREACH t IN ARRAY phi_tables LOOP
        -- Skip se la tabella non esiste (idempotenza forward-compat)
        IF NOT EXISTS (
            SELECT 1 FROM pg_tables
            WHERE schemaname = 'public' AND tablename = t
        ) THEN
            RAISE NOTICE 'Skipping non-existent table: %', t;
            CONTINUE;
        END IF;

        EXECUTE format('REVOKE ALL ON public.%I FROM anon', t);
        EXECUTE format('REVOKE ALL ON public.%I FROM authenticated', t);
        EXECUTE format(
            'GRANT SELECT, INSERT, UPDATE, DELETE ON public.%I TO authenticated',
            t
        );
    END LOOP;
END $$;

COMMIT;

-- =============================================================
-- Verifica post-apply (Supabase SQL editor):
--
--   SELECT table_name, grantee, privilege_type
--   FROM information_schema.role_table_grants
--   WHERE table_schema = 'public'
--     AND grantee IN ('anon', 'authenticated')
--     AND table_name IN (
--       'profiles','medications','dosing_schedules','supplies',
--       'prescriptions','prescription_requests','doctors','dose_events',
--       'routines','routine_steps','parameters','measurements',
--       'caregiver_relations','pending_changes','activity_logs',
--       'device_tokens','user_settings'
--     )
--   ORDER BY table_name, grantee;
--
--   Atteso:
--     - grantee `anon`        → 0 righe
--     - grantee `authenticated` → 4 righe per tabella (SELECT/INSERT/UPDATE/DELETE)
--
-- Nota:
--   Il client iOS continua a operare normalmente perché firma sempre con
--   un JWT `role: authenticated` (anche utenti anonimi via signInAnonymously).
-- =============================================================
