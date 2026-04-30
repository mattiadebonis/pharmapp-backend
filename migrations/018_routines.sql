-- ============================================================
-- Migration 018: Routines (lightweight medication sequences)
-- ============================================================
-- A routine groups 2+ medications taken in a precise temporal sequence,
-- with optional waits and events in between (e.g. osteoporosis morning
-- routine: Alendronato → wait 30min stomach empty → Calcio → breakfast).
--
-- Architectural rule: routine is a DECORATOR. Medications stay first-class
-- entities in the medications table. The routine orchestrates ORDER and
-- TIMING of existing medications without duplicating them.
--
-- A medication step's medication_id MUST reference a real medication.
-- When a routine takes ownership of a medication's timing, the
-- corresponding dosing_schedule's is_active flag is set to false on the
-- client (the routine's start_time + step offsets become the new source
-- of truth for when that medication fires).

CREATE TABLE IF NOT EXISTS routines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    -- RRULE-style frequency string. Example: "FREQ=WEEKLY;BYDAY=MO" for "lunedì"
    -- or "FREQ=DAILY" for "ogni giorno". Null until user sets it.
    rrule TEXT,
    -- Anchor time of day (HH:MM 24h) for the FIRST step. All other steps
    -- are offset from this anchor based on their position + wait durations.
    start_time TEXT,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_routines_profile_id ON routines(profile_id);

-- ============================================================
-- ROUTINE STEPS
-- ============================================================
-- One row per step in a routine, ordered by position (0-indexed).
--
-- step_type:
--   * medication: a real medication taken at this point. medication_id
--     points to the medications table. dose_amount is a free-text label
--     ("1 compressa", "35 mg", "2 capsule").
--   * wait: a measured wait between two steps. duration_minutes is the
--     wait length. instructions is an optional clinical note ("stomaco
--     vuoto").
--   * event: a daily-life action the patient confirms (Colazione, Doccia,
--     Vado al lavoro). event_name carries the label.

CREATE TABLE IF NOT EXISTS routine_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    routine_id UUID NOT NULL REFERENCES routines(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    step_type TEXT NOT NULL CHECK (step_type IN ('medication', 'wait', 'event')),
    -- medication step
    medication_id UUID REFERENCES medications(id) ON DELETE CASCADE,
    dose_amount TEXT,
    -- wait step
    duration_minutes INTEGER,
    instructions TEXT,
    -- event step
    event_name TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT routine_step_payload_consistent CHECK (
        (step_type = 'medication' AND medication_id IS NOT NULL)
        OR (step_type = 'wait' AND duration_minutes IS NOT NULL)
        OR (step_type = 'event' AND event_name IS NOT NULL)
    ),
    UNIQUE (routine_id, position)
);

CREATE INDEX IF NOT EXISTS idx_routine_steps_routine_id ON routine_steps(routine_id, position);
CREATE INDEX IF NOT EXISTS idx_routine_steps_medication_id ON routine_steps(medication_id) WHERE medication_id IS NOT NULL;

COMMENT ON TABLE routines IS
    'Lightweight ordered sequences of medications + waits + events. Decorator over medications, not a replacement.';
COMMENT ON COLUMN routines.rrule IS
    'RRULE frequency string (e.g. FREQ=WEEKLY;BYDAY=MO). Null until user picks frequency.';
COMMENT ON COLUMN routines.start_time IS
    'HH:MM anchor for the first step. All subsequent steps are offset by sum of preceding wait durations.';
COMMENT ON TABLE routine_steps IS
    'Ordered children of a routine. Three shapes: medication, wait, event. Constraint enforces required fields per shape.';
