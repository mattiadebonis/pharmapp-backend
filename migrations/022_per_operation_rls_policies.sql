-- =============================================================
-- Migration 022 — Per-operation RLS policies on PHI tables
-- =============================================================
-- Contesto:
--   La migration 001 ha creato policy `FOR ALL` su tutte le tabelle PHI.
--   Questa scelta concentra la logica in una singola policy per tabella,
--   ma viola il principio di defense in depth: se in futuro qualcuno
--   modifica la policy in modo errato (es. dimenticando il check su
--   INSERT), un singolo errore espone più operazioni contemporaneamente.
--
-- Obiettivo:
--   Sostituire ogni policy `FOR ALL` con 4 policy separate
--   (SELECT / INSERT / UPDATE / DELETE), ciascuna con `USING` e/o
--   `WITH CHECK` espliciti. Semantica identica all'attuale, ma:
--     1. Più auditabile: una policy = una operazione = un test.
--     2. Più resistente a regressioni: cambi a INSERT non toccano SELECT.
--     3. Compatibile con la checklist privacy-by-design del progetto.
--
-- Nota sulle differenze USING vs WITH CHECK:
--   - SELECT / DELETE: solo `USING` (filtra le righe visibili).
--   - INSERT: solo `WITH CHECK` (le righe ancora non esistono).
--   - UPDATE: entrambi (USING filtra le righe visibili, WITH CHECK
--     impedisce di "spostare" una riga fuori dal proprio scope).
--
-- Force RLS:
--   Aggiungiamo anche `FORCE ROW LEVEL SECURITY` per ogni tabella PHI:
--   senza questo flag, il proprietario della tabella (postgres role
--   nell'istanza Supabase) può bypassare RLS. service_role è una grant
--   role separata e continua a bypassare quando serve.
-- =============================================================

BEGIN;

-- ---------------------------------------------------------------
-- profiles
-- ---------------------------------------------------------------
DROP POLICY IF EXISTS profiles_owner ON public.profiles;

CREATE POLICY profiles_select ON public.profiles
    FOR SELECT TO authenticated
    USING (user_id = auth.uid());

CREATE POLICY profiles_insert ON public.profiles
    FOR INSERT TO authenticated
    WITH CHECK (user_id = auth.uid());

CREATE POLICY profiles_update ON public.profiles
    FOR UPDATE TO authenticated
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

CREATE POLICY profiles_delete ON public.profiles
    FOR DELETE TO authenticated
    USING (user_id = auth.uid());

ALTER TABLE public.profiles FORCE ROW LEVEL SECURITY;


-- ---------------------------------------------------------------
-- medications (nested ownership through profiles)
-- ---------------------------------------------------------------
DROP POLICY IF EXISTS medications_owner ON public.medications;

CREATE POLICY medications_select ON public.medications
    FOR SELECT TO authenticated
    USING (profile_id IN (SELECT id FROM public.profiles WHERE user_id = auth.uid()));

CREATE POLICY medications_insert ON public.medications
    FOR INSERT TO authenticated
    WITH CHECK (profile_id IN (SELECT id FROM public.profiles WHERE user_id = auth.uid()));

CREATE POLICY medications_update ON public.medications
    FOR UPDATE TO authenticated
    USING (profile_id IN (SELECT id FROM public.profiles WHERE user_id = auth.uid()))
    WITH CHECK (profile_id IN (SELECT id FROM public.profiles WHERE user_id = auth.uid()));

CREATE POLICY medications_delete ON public.medications
    FOR DELETE TO authenticated
    USING (profile_id IN (SELECT id FROM public.profiles WHERE user_id = auth.uid()));

ALTER TABLE public.medications FORCE ROW LEVEL SECURITY;


-- ---------------------------------------------------------------
-- dosing_schedules (nested through medications -> profiles)
-- ---------------------------------------------------------------
DROP POLICY IF EXISTS dosing_schedules_owner ON public.dosing_schedules;

CREATE POLICY dosing_schedules_select ON public.dosing_schedules
    FOR SELECT TO authenticated
    USING (medication_id IN (
        SELECT m.id FROM public.medications m
        JOIN public.profiles p ON p.id = m.profile_id
        WHERE p.user_id = auth.uid()
    ));

CREATE POLICY dosing_schedules_insert ON public.dosing_schedules
    FOR INSERT TO authenticated
    WITH CHECK (medication_id IN (
        SELECT m.id FROM public.medications m
        JOIN public.profiles p ON p.id = m.profile_id
        WHERE p.user_id = auth.uid()
    ));

CREATE POLICY dosing_schedules_update ON public.dosing_schedules
    FOR UPDATE TO authenticated
    USING (medication_id IN (
        SELECT m.id FROM public.medications m
        JOIN public.profiles p ON p.id = m.profile_id
        WHERE p.user_id = auth.uid()
    ))
    WITH CHECK (medication_id IN (
        SELECT m.id FROM public.medications m
        JOIN public.profiles p ON p.id = m.profile_id
        WHERE p.user_id = auth.uid()
    ));

CREATE POLICY dosing_schedules_delete ON public.dosing_schedules
    FOR DELETE TO authenticated
    USING (medication_id IN (
        SELECT m.id FROM public.medications m
        JOIN public.profiles p ON p.id = m.profile_id
        WHERE p.user_id = auth.uid()
    ));

ALTER TABLE public.dosing_schedules FORCE ROW LEVEL SECURITY;


-- ---------------------------------------------------------------
-- supplies (nested through medications)
-- ---------------------------------------------------------------
DROP POLICY IF EXISTS supplies_owner ON public.supplies;

CREATE POLICY supplies_select ON public.supplies
    FOR SELECT TO authenticated
    USING (medication_id IN (
        SELECT m.id FROM public.medications m
        JOIN public.profiles p ON p.id = m.profile_id
        WHERE p.user_id = auth.uid()
    ));

CREATE POLICY supplies_insert ON public.supplies
    FOR INSERT TO authenticated
    WITH CHECK (medication_id IN (
        SELECT m.id FROM public.medications m
        JOIN public.profiles p ON p.id = m.profile_id
        WHERE p.user_id = auth.uid()
    ));

CREATE POLICY supplies_update ON public.supplies
    FOR UPDATE TO authenticated
    USING (medication_id IN (
        SELECT m.id FROM public.medications m
        JOIN public.profiles p ON p.id = m.profile_id
        WHERE p.user_id = auth.uid()
    ))
    WITH CHECK (medication_id IN (
        SELECT m.id FROM public.medications m
        JOIN public.profiles p ON p.id = m.profile_id
        WHERE p.user_id = auth.uid()
    ));

CREATE POLICY supplies_delete ON public.supplies
    FOR DELETE TO authenticated
    USING (medication_id IN (
        SELECT m.id FROM public.medications m
        JOIN public.profiles p ON p.id = m.profile_id
        WHERE p.user_id = auth.uid()
    ));

ALTER TABLE public.supplies FORCE ROW LEVEL SECURITY;


-- ---------------------------------------------------------------
-- prescriptions (nested through medications)
-- ---------------------------------------------------------------
DROP POLICY IF EXISTS prescriptions_owner ON public.prescriptions;

CREATE POLICY prescriptions_select ON public.prescriptions
    FOR SELECT TO authenticated
    USING (medication_id IN (
        SELECT m.id FROM public.medications m
        JOIN public.profiles p ON p.id = m.profile_id
        WHERE p.user_id = auth.uid()
    ));

CREATE POLICY prescriptions_insert ON public.prescriptions
    FOR INSERT TO authenticated
    WITH CHECK (medication_id IN (
        SELECT m.id FROM public.medications m
        JOIN public.profiles p ON p.id = m.profile_id
        WHERE p.user_id = auth.uid()
    ));

CREATE POLICY prescriptions_update ON public.prescriptions
    FOR UPDATE TO authenticated
    USING (medication_id IN (
        SELECT m.id FROM public.medications m
        JOIN public.profiles p ON p.id = m.profile_id
        WHERE p.user_id = auth.uid()
    ))
    WITH CHECK (medication_id IN (
        SELECT m.id FROM public.medications m
        JOIN public.profiles p ON p.id = m.profile_id
        WHERE p.user_id = auth.uid()
    ));

CREATE POLICY prescriptions_delete ON public.prescriptions
    FOR DELETE TO authenticated
    USING (medication_id IN (
        SELECT m.id FROM public.medications m
        JOIN public.profiles p ON p.id = m.profile_id
        WHERE p.user_id = auth.uid()
    ));

ALTER TABLE public.prescriptions FORCE ROW LEVEL SECURITY;


-- ---------------------------------------------------------------
-- prescription_requests (nested through medications)
-- ---------------------------------------------------------------
DROP POLICY IF EXISTS prescription_requests_owner ON public.prescription_requests;

CREATE POLICY prescription_requests_select ON public.prescription_requests
    FOR SELECT TO authenticated
    USING (medication_id IN (
        SELECT m.id FROM public.medications m
        JOIN public.profiles p ON p.id = m.profile_id
        WHERE p.user_id = auth.uid()
    ));

CREATE POLICY prescription_requests_insert ON public.prescription_requests
    FOR INSERT TO authenticated
    WITH CHECK (medication_id IN (
        SELECT m.id FROM public.medications m
        JOIN public.profiles p ON p.id = m.profile_id
        WHERE p.user_id = auth.uid()
    ));

CREATE POLICY prescription_requests_update ON public.prescription_requests
    FOR UPDATE TO authenticated
    USING (medication_id IN (
        SELECT m.id FROM public.medications m
        JOIN public.profiles p ON p.id = m.profile_id
        WHERE p.user_id = auth.uid()
    ))
    WITH CHECK (medication_id IN (
        SELECT m.id FROM public.medications m
        JOIN public.profiles p ON p.id = m.profile_id
        WHERE p.user_id = auth.uid()
    ));

CREATE POLICY prescription_requests_delete ON public.prescription_requests
    FOR DELETE TO authenticated
    USING (medication_id IN (
        SELECT m.id FROM public.medications m
        JOIN public.profiles p ON p.id = m.profile_id
        WHERE p.user_id = auth.uid()
    ));

ALTER TABLE public.prescription_requests FORCE ROW LEVEL SECURITY;


-- ---------------------------------------------------------------
-- doctors
-- ---------------------------------------------------------------
DROP POLICY IF EXISTS doctors_owner ON public.doctors;

CREATE POLICY doctors_select ON public.doctors
    FOR SELECT TO authenticated USING (user_id = auth.uid());
CREATE POLICY doctors_insert ON public.doctors
    FOR INSERT TO authenticated WITH CHECK (user_id = auth.uid());
CREATE POLICY doctors_update ON public.doctors
    FOR UPDATE TO authenticated USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());
CREATE POLICY doctors_delete ON public.doctors
    FOR DELETE TO authenticated USING (user_id = auth.uid());

ALTER TABLE public.doctors FORCE ROW LEVEL SECURITY;


-- ---------------------------------------------------------------
-- dose_events (nested through profile)
-- ---------------------------------------------------------------
DROP POLICY IF EXISTS dose_events_owner ON public.dose_events;

CREATE POLICY dose_events_select ON public.dose_events
    FOR SELECT TO authenticated
    USING (profile_id IN (SELECT id FROM public.profiles WHERE user_id = auth.uid()));

CREATE POLICY dose_events_insert ON public.dose_events
    FOR INSERT TO authenticated
    WITH CHECK (profile_id IN (SELECT id FROM public.profiles WHERE user_id = auth.uid()));

CREATE POLICY dose_events_update ON public.dose_events
    FOR UPDATE TO authenticated
    USING (profile_id IN (SELECT id FROM public.profiles WHERE user_id = auth.uid()))
    WITH CHECK (profile_id IN (SELECT id FROM public.profiles WHERE user_id = auth.uid()));

CREATE POLICY dose_events_delete ON public.dose_events
    FOR DELETE TO authenticated
    USING (profile_id IN (SELECT id FROM public.profiles WHERE user_id = auth.uid()));

ALTER TABLE public.dose_events FORCE ROW LEVEL SECURITY;


-- ---------------------------------------------------------------
-- caregiver_relations (patient OR caregiver)
-- ---------------------------------------------------------------
DROP POLICY IF EXISTS caregiver_relations_access ON public.caregiver_relations;

CREATE POLICY caregiver_relations_select ON public.caregiver_relations
    FOR SELECT TO authenticated
    USING (patient_user_id = auth.uid() OR caregiver_user_id = auth.uid());

-- Solo il patient può creare un invito (invitando un caregiver). Il
-- caregiver è autorizzato a UPDATE per il flusso di acceptance.
CREATE POLICY caregiver_relations_insert ON public.caregiver_relations
    FOR INSERT TO authenticated
    WITH CHECK (patient_user_id = auth.uid());

CREATE POLICY caregiver_relations_update ON public.caregiver_relations
    FOR UPDATE TO authenticated
    USING (patient_user_id = auth.uid() OR caregiver_user_id = auth.uid())
    WITH CHECK (patient_user_id = auth.uid() OR caregiver_user_id = auth.uid());

CREATE POLICY caregiver_relations_delete ON public.caregiver_relations
    FOR DELETE TO authenticated
    USING (patient_user_id = auth.uid() OR caregiver_user_id = auth.uid());

ALTER TABLE public.caregiver_relations FORCE ROW LEVEL SECURITY;


-- ---------------------------------------------------------------
-- pending_changes (through caregiver_relations)
-- ---------------------------------------------------------------
DROP POLICY IF EXISTS pending_changes_access ON public.pending_changes;

CREATE POLICY pending_changes_select ON public.pending_changes
    FOR SELECT TO authenticated
    USING (caregiver_relation_id IN (
        SELECT id FROM public.caregiver_relations
        WHERE patient_user_id = auth.uid() OR caregiver_user_id = auth.uid()
    ));

CREATE POLICY pending_changes_insert ON public.pending_changes
    FOR INSERT TO authenticated
    WITH CHECK (caregiver_relation_id IN (
        SELECT id FROM public.caregiver_relations
        WHERE patient_user_id = auth.uid() OR caregiver_user_id = auth.uid()
    ));

CREATE POLICY pending_changes_update ON public.pending_changes
    FOR UPDATE TO authenticated
    USING (caregiver_relation_id IN (
        SELECT id FROM public.caregiver_relations
        WHERE patient_user_id = auth.uid() OR caregiver_user_id = auth.uid()
    ))
    WITH CHECK (caregiver_relation_id IN (
        SELECT id FROM public.caregiver_relations
        WHERE patient_user_id = auth.uid() OR caregiver_user_id = auth.uid()
    ));

CREATE POLICY pending_changes_delete ON public.pending_changes
    FOR DELETE TO authenticated
    USING (caregiver_relation_id IN (
        SELECT id FROM public.caregiver_relations
        WHERE patient_user_id = auth.uid() OR caregiver_user_id = auth.uid()
    ));

ALTER TABLE public.pending_changes FORCE ROW LEVEL SECURITY;


-- ---------------------------------------------------------------
-- activity_logs
-- Note: storia, append-mostly. Dovremmo bloccare UPDATE/DELETE da
-- client per garantirne l'immutabilità (audit trail). Per ora
-- replichiamo la semantica esistente; vedi migration 024 per la
-- versione audit-grade su schema separato.
-- ---------------------------------------------------------------
DROP POLICY IF EXISTS activity_logs_owner ON public.activity_logs;

CREATE POLICY activity_logs_select ON public.activity_logs
    FOR SELECT TO authenticated USING (user_id = auth.uid());
CREATE POLICY activity_logs_insert ON public.activity_logs
    FOR INSERT TO authenticated WITH CHECK (user_id = auth.uid());
CREATE POLICY activity_logs_update ON public.activity_logs
    FOR UPDATE TO authenticated USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());
CREATE POLICY activity_logs_delete ON public.activity_logs
    FOR DELETE TO authenticated USING (user_id = auth.uid());

ALTER TABLE public.activity_logs FORCE ROW LEVEL SECURITY;


-- ---------------------------------------------------------------
-- device_tokens
-- ---------------------------------------------------------------
DROP POLICY IF EXISTS device_tokens_owner ON public.device_tokens;

CREATE POLICY device_tokens_select ON public.device_tokens
    FOR SELECT TO authenticated USING (user_id = auth.uid());
CREATE POLICY device_tokens_insert ON public.device_tokens
    FOR INSERT TO authenticated WITH CHECK (user_id = auth.uid());
CREATE POLICY device_tokens_update ON public.device_tokens
    FOR UPDATE TO authenticated USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());
CREATE POLICY device_tokens_delete ON public.device_tokens
    FOR DELETE TO authenticated USING (user_id = auth.uid());

ALTER TABLE public.device_tokens FORCE ROW LEVEL SECURITY;


-- ---------------------------------------------------------------
-- user_settings
-- ---------------------------------------------------------------
DROP POLICY IF EXISTS user_settings_owner ON public.user_settings;

CREATE POLICY user_settings_select ON public.user_settings
    FOR SELECT TO authenticated USING (user_id = auth.uid());
CREATE POLICY user_settings_insert ON public.user_settings
    FOR INSERT TO authenticated WITH CHECK (user_id = auth.uid());
CREATE POLICY user_settings_update ON public.user_settings
    FOR UPDATE TO authenticated USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());
CREATE POLICY user_settings_delete ON public.user_settings
    FOR DELETE TO authenticated USING (user_id = auth.uid());

ALTER TABLE public.user_settings FORCE ROW LEVEL SECURITY;


-- ---------------------------------------------------------------
-- routines (nested through profile)
-- ---------------------------------------------------------------
DROP POLICY IF EXISTS routines_owner ON public.routines;

CREATE POLICY routines_select ON public.routines
    FOR SELECT TO authenticated
    USING (profile_id IN (SELECT id FROM public.profiles WHERE user_id = auth.uid()));
CREATE POLICY routines_insert ON public.routines
    FOR INSERT TO authenticated
    WITH CHECK (profile_id IN (SELECT id FROM public.profiles WHERE user_id = auth.uid()));
CREATE POLICY routines_update ON public.routines
    FOR UPDATE TO authenticated
    USING (profile_id IN (SELECT id FROM public.profiles WHERE user_id = auth.uid()))
    WITH CHECK (profile_id IN (SELECT id FROM public.profiles WHERE user_id = auth.uid()));
CREATE POLICY routines_delete ON public.routines
    FOR DELETE TO authenticated
    USING (profile_id IN (SELECT id FROM public.profiles WHERE user_id = auth.uid()));

ALTER TABLE public.routines FORCE ROW LEVEL SECURITY;


-- ---------------------------------------------------------------
-- routine_steps (nested through routine -> profile)
-- ---------------------------------------------------------------
DROP POLICY IF EXISTS routine_steps_owner ON public.routine_steps;

CREATE POLICY routine_steps_select ON public.routine_steps
    FOR SELECT TO authenticated
    USING (routine_id IN (
        SELECT r.id FROM public.routines r
        JOIN public.profiles p ON p.id = r.profile_id
        WHERE p.user_id = auth.uid()
    ));
CREATE POLICY routine_steps_insert ON public.routine_steps
    FOR INSERT TO authenticated
    WITH CHECK (routine_id IN (
        SELECT r.id FROM public.routines r
        JOIN public.profiles p ON p.id = r.profile_id
        WHERE p.user_id = auth.uid()
    ));
CREATE POLICY routine_steps_update ON public.routine_steps
    FOR UPDATE TO authenticated
    USING (routine_id IN (
        SELECT r.id FROM public.routines r
        JOIN public.profiles p ON p.id = r.profile_id
        WHERE p.user_id = auth.uid()
    ))
    WITH CHECK (routine_id IN (
        SELECT r.id FROM public.routines r
        JOIN public.profiles p ON p.id = r.profile_id
        WHERE p.user_id = auth.uid()
    ));
CREATE POLICY routine_steps_delete ON public.routine_steps
    FOR DELETE TO authenticated
    USING (routine_id IN (
        SELECT r.id FROM public.routines r
        JOIN public.profiles p ON p.id = r.profile_id
        WHERE p.user_id = auth.uid()
    ));

ALTER TABLE public.routine_steps FORCE ROW LEVEL SECURITY;


-- ---------------------------------------------------------------
-- parameters (nested through profile)
-- ---------------------------------------------------------------
DROP POLICY IF EXISTS parameters_owner ON public.parameters;

CREATE POLICY parameters_select ON public.parameters
    FOR SELECT TO authenticated
    USING (profile_id IN (SELECT id FROM public.profiles WHERE user_id = auth.uid()));
CREATE POLICY parameters_insert ON public.parameters
    FOR INSERT TO authenticated
    WITH CHECK (profile_id IN (SELECT id FROM public.profiles WHERE user_id = auth.uid()));
CREATE POLICY parameters_update ON public.parameters
    FOR UPDATE TO authenticated
    USING (profile_id IN (SELECT id FROM public.profiles WHERE user_id = auth.uid()))
    WITH CHECK (profile_id IN (SELECT id FROM public.profiles WHERE user_id = auth.uid()));
CREATE POLICY parameters_delete ON public.parameters
    FOR DELETE TO authenticated
    USING (profile_id IN (SELECT id FROM public.profiles WHERE user_id = auth.uid()));

ALTER TABLE public.parameters FORCE ROW LEVEL SECURITY;


-- ---------------------------------------------------------------
-- measurements (nested through profile)
-- ---------------------------------------------------------------
DROP POLICY IF EXISTS measurements_owner ON public.measurements;

CREATE POLICY measurements_select ON public.measurements
    FOR SELECT TO authenticated
    USING (profile_id IN (SELECT id FROM public.profiles WHERE user_id = auth.uid()));
CREATE POLICY measurements_insert ON public.measurements
    FOR INSERT TO authenticated
    WITH CHECK (profile_id IN (SELECT id FROM public.profiles WHERE user_id = auth.uid()));
CREATE POLICY measurements_update ON public.measurements
    FOR UPDATE TO authenticated
    USING (profile_id IN (SELECT id FROM public.profiles WHERE user_id = auth.uid()))
    WITH CHECK (profile_id IN (SELECT id FROM public.profiles WHERE user_id = auth.uid()));
CREATE POLICY measurements_delete ON public.measurements
    FOR DELETE TO authenticated
    USING (profile_id IN (SELECT id FROM public.profiles WHERE user_id = auth.uid()));

ALTER TABLE public.measurements FORCE ROW LEVEL SECURITY;


COMMIT;

-- =============================================================
-- Verifica post-apply (Supabase SQL editor):
--
--   SELECT schemaname, tablename, policyname, cmd
--   FROM pg_policies
--   WHERE schemaname = 'public'
--     AND tablename IN (
--       'profiles','medications','dosing_schedules','supplies',
--       'prescriptions','prescription_requests','doctors','dose_events',
--       'caregiver_relations','pending_changes','activity_logs',
--       'device_tokens','user_settings','routines','routine_steps',
--       'parameters','measurements'
--     )
--   ORDER BY tablename, cmd;
--
--   Atteso: 4 righe per ogni tabella PHI (SELECT/INSERT/UPDATE/DELETE),
--   nessuna policy con cmd='ALL' su queste tabelle.
--
--   SELECT tablename FROM pg_tables
--   WHERE schemaname = 'public' AND rowsecurity = TRUE AND forcerowsecurity = TRUE;
--
--   Atteso: tutte le 17 tabelle PHI elencate sopra.
-- =============================================================
