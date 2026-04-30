-- ============================================================
-- Migration 019: Complete routines (RLS, triggers, measurement step,
-- managed_by_routine_id)
-- ============================================================
-- Closes the gaps left by migration 018:
--   1. RLS policies on routines + routine_steps (owner = profile.user_id)
--   2. updated_at triggers (consistency with the rest of the schema)
--   3. New step_type 'measurement' + parameter_key column
--   4. medications.managed_by_routine_id link (avoids double scheduling
--      when a med's timing is delegated to a routine)
--
-- DOES NOT modify migration 018 in place — it adds atop. Safe to apply
-- on environments where 018 is already in production.

-- ------------------------------------------------------------
-- 1. RLS
-- ------------------------------------------------------------
ALTER TABLE routines ENABLE ROW LEVEL SECURITY;
CREATE POLICY routines_owner ON routines FOR ALL USING (
    profile_id IN (SELECT id FROM profiles WHERE user_id = auth.uid())
);

ALTER TABLE routine_steps ENABLE ROW LEVEL SECURITY;
CREATE POLICY routine_steps_owner ON routine_steps FOR ALL USING (
    routine_id IN (
        SELECT r.id FROM routines r
        JOIN profiles p ON p.id = r.profile_id
        WHERE p.user_id = auth.uid()
    )
);

-- ------------------------------------------------------------
-- 2. updated_at triggers
-- ------------------------------------------------------------
CREATE TRIGGER routines_updated_at BEFORE UPDATE ON routines
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER routine_steps_updated_at BEFORE UPDATE ON routine_steps
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ------------------------------------------------------------
-- 3. New step_type 'measurement' + parameter_key
-- ------------------------------------------------------------
-- Drop the old constraints (named per Postgres conventions on the
-- 018 schema). The check name was auto-generated; we use IF EXISTS
-- to be safe across environments where the name may differ.
ALTER TABLE routine_steps DROP CONSTRAINT IF EXISTS routine_step_payload_consistent;
ALTER TABLE routine_steps DROP CONSTRAINT IF EXISTS routine_steps_step_type_check;

ALTER TABLE routine_steps
    ADD CONSTRAINT routine_steps_step_type_check
    CHECK (step_type IN ('medication', 'wait', 'event', 'measurement'));

ALTER TABLE routine_steps ADD COLUMN IF NOT EXISTS parameter_key TEXT;

ALTER TABLE routine_steps
    ADD CONSTRAINT routine_step_payload_consistent CHECK (
        (step_type = 'medication' AND medication_id IS NOT NULL)
        OR (step_type = 'wait' AND duration_minutes IS NOT NULL)
        OR (step_type = 'event' AND event_name IS NOT NULL)
        OR (step_type = 'measurement' AND parameter_key IS NOT NULL)
    );

CREATE INDEX IF NOT EXISTS idx_routine_steps_parameter_key
    ON routine_steps(parameter_key)
    WHERE parameter_key IS NOT NULL;

COMMENT ON COLUMN routine_steps.parameter_key IS
    'For step_type=measurement: identifier of the parameter to record. Predefined keys (e.g. ''glycemia'', ''blood_pressure'') are hard-coded in Python; custom parameters use the format ''custom:<uuid>'' and have a row in the parameters table.';

-- ------------------------------------------------------------
-- 4. medications.managed_by_routine_id
-- ------------------------------------------------------------
-- Set when a medication is added as a step inside a routine. The
-- medication's dosing_schedules are deactivated (is_active=false) and
-- the routine becomes the source of truth for timing. ON DELETE
-- SET NULL: if the routine is deleted, the medication remains but
-- becomes unmanaged (the application layer is responsible for
-- restoring/reactivating its schedule, or deleting the medication
-- entirely per product spec).
ALTER TABLE medications ADD COLUMN IF NOT EXISTS managed_by_routine_id UUID
    REFERENCES routines(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_medications_managed_by_routine
    ON medications(managed_by_routine_id)
    WHERE managed_by_routine_id IS NOT NULL;

COMMENT ON COLUMN medications.managed_by_routine_id IS
    'When non-null, the medication''s timing is delegated to this routine. Its dosing_schedules.is_active should be false.';
