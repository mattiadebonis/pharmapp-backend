-- =============================================================
-- Migration 024 — Dedicated `audit` schema for access trail
-- =============================================================
-- Contesto:
--   Oggi `activity_logs` (in `public`) raccoglie sia gli eventi di
--   business (es. "user took dose X") sia, di fatto, gli accessi —
--   quando il backend logga manualmente. Il problema è che lo stesso
--   client può anche modificare/cancellare le righe della tabella,
--   il che invalida l'audit trail.
--
-- Obiettivo:
--   1. Schema separato `audit` per gli access-log.
--   2. Tabella `audit.access_log` configurata insert-only da client:
--      RLS permette INSERT solo dell'utente stesso, SELECT solo delle
--      proprie righe, **niente** UPDATE/DELETE — nemmeno per il
--      proprietario del dato.
--   3. service_role (backend) bypassa, quindi può popolare la tabella
--      con info aggiuntive che il client da solo non vede (es. l'IP
--      sanitizzato, il request_id) tramite `app/services/audit_service.py`
--      che verrà introdotto a parte.
--
-- Migrazione del payload da activity_logs:
--   Non spostiamo automaticamente i record esistenti. Questa migration
--   crea solo la struttura. Una migration successiva o il rollout
--   dell'audit_service in produzione popolerà progressivamente la
--   tabella nuova; il vecchio activity_logs resta per compatibilità
--   con la UI corrente.
-- =============================================================

BEGIN;

-- ---------------------------------------------------------------
-- 1. Schema
-- ---------------------------------------------------------------

CREATE SCHEMA IF NOT EXISTS audit;

-- Default revoke per evitare di concedere a `anon` o `public`.
REVOKE ALL ON SCHEMA audit FROM PUBLIC;
GRANT USAGE ON SCHEMA audit TO authenticated, service_role;


-- ---------------------------------------------------------------
-- 2. Tabella access_log
-- ---------------------------------------------------------------

CREATE TABLE IF NOT EXISTS audit.access_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Chi ha eseguito l'azione (autenticato).
    actor_user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    -- Su quale utente impatta (== actor per accessi self; diverso per
    -- caregiver che legge dati del paziente).
    target_user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    -- Tabella PHI toccata, in formato 'public.medications'.
    resource_table TEXT NOT NULL CHECK (length(resource_table) BETWEEN 1 AND 80),
    -- ID specifico dell'oggetto. NULL per query in lista (audit
    -- aggregato), UUID per accesso a singola riga.
    resource_id UUID,
    -- Tipo di operazione, vincolato per evitare valori liberi.
    action TEXT NOT NULL CHECK (action IN ('select','insert','update','delete')),
    -- Canale di accesso: l'utente sui propri dati, un caregiver, un job
    -- amministrativo via service_role.
    via TEXT NOT NULL CHECK (via IN ('owner','caregiver','admin')),
    -- Correlazione con un singolo HTTP request (X-Request-Id).
    request_id TEXT CHECK (request_id IS NULL OR length(request_id) <= 80),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_access_target_recent
    ON audit.access_log (target_user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_access_actor_recent
    ON audit.access_log (actor_user_id, created_at DESC);


-- ---------------------------------------------------------------
-- 3. RLS — insert-only da client
-- ---------------------------------------------------------------
ALTER TABLE audit.access_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit.access_log FORCE ROW LEVEL SECURITY;

-- Inserimento: l'utente può registrare solo righe in cui figura come
-- attore. Il backend (service_role) bypassa e può registrare qualunque
-- riga (incluso `via='caregiver'` per conto di un caregiver).
CREATE POLICY audit_access_insert ON audit.access_log
    FOR INSERT TO authenticated
    WITH CHECK (actor_user_id = auth.uid());

-- Lettura: l'utente vede le righe in cui è attore o target.
CREATE POLICY audit_access_select ON audit.access_log
    FOR SELECT TO authenticated
    USING (actor_user_id = auth.uid() OR target_user_id = auth.uid());

-- Niente policy UPDATE/DELETE → operazioni implicitamente negate da RLS.

-- Default grants: revoke aggressivo, poi rilascia solo l'indispensabile.
REVOKE ALL ON audit.access_log FROM anon, authenticated;
GRANT SELECT, INSERT ON audit.access_log TO authenticated;


-- ---------------------------------------------------------------
-- 4. Trigger di immutabilità (belt and suspenders)
-- ---------------------------------------------------------------
-- Le RLS policy bloccano già UPDATE/DELETE, ma un superuser potrebbe
-- aggirare le policy. Il trigger BEFORE rifiuta sempre UPDATE/DELETE
-- a livello di tabella, indipendentemente dal ruolo (eccetto NOLOGIN
-- maintenance role esplicitamente concesso).

CREATE OR REPLACE FUNCTION audit.reject_mutations()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = audit, pg_temp
AS $$
BEGIN
    RAISE EXCEPTION 'audit.access_log is append-only (no % allowed)', TG_OP
        USING ERRCODE = 'insufficient_privilege';
END;
$$;

DROP TRIGGER IF EXISTS audit_access_log_no_update ON audit.access_log;
CREATE TRIGGER audit_access_log_no_update
    BEFORE UPDATE ON audit.access_log
    FOR EACH ROW EXECUTE FUNCTION audit.reject_mutations();

DROP TRIGGER IF EXISTS audit_access_log_no_delete ON audit.access_log;
CREATE TRIGGER audit_access_log_no_delete
    BEFORE DELETE ON audit.access_log
    FOR EACH ROW EXECUTE FUNCTION audit.reject_mutations();


COMMIT;

-- =============================================================
-- Verifica post-apply (Supabase SQL editor):
--
--   -- 1. Schema visibile, tabella creata, RLS forzato:
--   SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'audit';
--   SELECT relname, relrowsecurity, relforcerowsecurity
--     FROM pg_class WHERE oid = 'audit.access_log'::regclass;
--
--   -- 2. Policy create:
--   SELECT polname, polcmd FROM pg_policy
--     WHERE polrelid = 'audit.access_log'::regclass;
--   -- atteso: due righe (insert, select). Niente update/delete.
--
--   -- 3. Tentare UPDATE/DELETE come authenticated → errore.
--   --    (eseguire in sessione user) → "audit.access_log is append-only"
-- =============================================================
