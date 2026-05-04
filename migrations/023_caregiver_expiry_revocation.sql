-- =============================================================
-- Migration 023 — Caregiver relations: expiry + revocation timestamps
-- =============================================================
-- Contesto:
--   La tabella `caregiver_relations` ha oggi un campo `status` (testo)
--   con valori 'pending'/'patient_confirmation'/'active'/'rejected'/
--   'revoked'. Questo è sufficiente per visualizzare lo stato corrente
--   ma:
--     1. Non c'è scadenza automatica della relazione: una volta 'active'
--        il caregiver mantiene l'accesso indefinitamente.
--     2. Quando viene revocata, perdiamo la timestamp dell'evento, e
--        questo è un dato necessario per audit GDPR (art. 9, dati
--        sanitari).
--
-- Obiettivo:
--   Aggiungere due colonne:
--     - `expires_at TIMESTAMPTZ NULL` — scadenza opzionale; NULL = mai.
--       Default applicato a 12 mesi dalla creazione, override possibile
--       lato API in una iterazione futura.
--     - `revoked_at TIMESTAMPTZ NULL` — non-NULL quando la relazione è
--       stata revocata. Popolato anche per le righe esistenti con
--       `status = 'revoked'` per consistenza storica.
--
--   Estendere le RLS policy create in 022 per controllare sia la
--   scadenza sia la revoca: una relazione con `revoked_at IS NOT NULL`
--   o `expires_at < now()` non concede più accesso al caregiver,
--   anche se la riga è ancora visibile per ragioni di audit.
--
-- Backwards compat:
--   Il backend FastAPI usa service_role e bypassa RLS, quindi vede
--   sempre tutte le righe. Il client iOS via PostgREST è quello che
--   beneficia dell'irrigidimento delle policy.
-- =============================================================

BEGIN;

-- ---------------------------------------------------------------
-- 1. Schema additions
-- ---------------------------------------------------------------

ALTER TABLE public.caregiver_relations
    ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS revoked_at TIMESTAMPTZ;

-- Backfill: per le righe esistenti con status = 'revoked', imposta
-- revoked_at = updated_at (il momento più recente in cui è stato
-- toccato lo stato — best-effort).
UPDATE public.caregiver_relations
SET revoked_at = updated_at
WHERE status = 'revoked' AND revoked_at IS NULL;

-- Backfill: per le righe attive non scadute, imposta una scadenza a
-- 12 mesi dalla data di creazione. Le relazioni nate ora avranno la
-- scadenza fissata dal backend al momento dell'accept.
UPDATE public.caregiver_relations
SET expires_at = created_at + INTERVAL '12 months'
WHERE status = 'active' AND expires_at IS NULL;


-- ---------------------------------------------------------------
-- 2. Index per query "relazioni attive non scadute"
-- ---------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_caregiver_active_window
    ON public.caregiver_relations (caregiver_user_id, expires_at)
    WHERE revoked_at IS NULL;


-- ---------------------------------------------------------------
-- 3. RLS — refactor della policy SELECT per includere expiry/revoke
-- ---------------------------------------------------------------
-- La policy 022 lasciava "patient OR caregiver" senza vincoli temporali.
-- Ora il caregiver vede la relazione SOLO se non è stata revocata e
-- non è scaduta. Il paziente continua a vedere sempre, perché lui ha
-- bisogno di gestire revoca/rinnovo della relazione anche storica.

DROP POLICY IF EXISTS caregiver_relations_select ON public.caregiver_relations;

CREATE POLICY caregiver_relations_select ON public.caregiver_relations
    FOR SELECT TO authenticated
    USING (
        -- Il paziente vede sempre tutte le sue relazioni (anche revocate).
        patient_user_id = auth.uid()
        OR (
            -- Il caregiver vede SOLO relazioni attive nel tempo.
            caregiver_user_id = auth.uid()
            AND revoked_at IS NULL
            AND (expires_at IS NULL OR expires_at > now())
        )
    );


-- ---------------------------------------------------------------
-- 4. Helper RLS function: relazione caregiver attiva al momento `t`
-- ---------------------------------------------------------------
-- Pensata per essere riusata dalle policy caregiver-aware su tabelle
-- di terze parti (es. medications/dose_events) quando in futuro il
-- caregiver potrà leggerle. Oggi quelle policy non danno ancora
-- accesso al caregiver — questa funzione è la fondamenta su cui
-- costruirla.

CREATE OR REPLACE FUNCTION public.is_caregiver_active_for(patient UUID)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.caregiver_relations
        WHERE patient_user_id = patient
          AND caregiver_user_id = auth.uid()
          AND status = 'active'
          AND revoked_at IS NULL
          AND (expires_at IS NULL OR expires_at > now())
    );
$$;

REVOKE EXECUTE ON FUNCTION public.is_caregiver_active_for(UUID) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.is_caregiver_active_for(UUID) TO authenticated, service_role;


COMMIT;

-- =============================================================
-- Verifica post-apply:
--
--   -- 1. Backfill applicato:
--   SELECT count(*) FROM public.caregiver_relations
--   WHERE status = 'active' AND expires_at IS NULL;
--   -- atteso: 0
--
--   SELECT count(*) FROM public.caregiver_relations
--   WHERE status = 'revoked' AND revoked_at IS NULL;
--   -- atteso: 0
--
--   -- 2. RLS: caregiver scaduto non vede più la riga.
--   --    (eseguire in sessione caregiver) — atteso: 0 righe.
--   UPDATE public.caregiver_relations SET expires_at = now() - INTERVAL '1 day'
--     WHERE id = '<test-id>';
--   SELECT * FROM public.caregiver_relations WHERE id = '<test-id>';
-- =============================================================
