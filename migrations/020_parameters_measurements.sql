-- ============================================================
-- Migration 020: Parameters + Measurements
-- ============================================================
-- Parameters describe what to measure (glycemia, blood_pressure, weight,
-- INR, …). Predefined ones live in Python — the `parameters` table only
-- holds USER-CUSTOM parameters, identified by `parameter_key='custom:<uuid>'`.
--
-- Measurements record values entered by the user (or a caregiver).
-- Polymorphic value columns: only one populated based on the parameter's
-- value_type.

-- ------------------------------------------------------------
-- Parameters (custom only — predefined are hard-coded in Python)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS parameters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    parameter_key TEXT NOT NULL,
    name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 40),
    unit TEXT CHECK (unit IS NULL OR length(unit) <= 20),
    value_type TEXT NOT NULL
        CHECK (value_type IN ('numericSingle', 'numericDouble', 'text')),
    -- Optional labels for numericDouble (e.g. ["Sistolica", "Diastolica"])
    labels JSONB,
    decimals INTEGER CHECK (decimals IS NULL OR (decimals >= 0 AND decimals <= 4)),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (profile_id, parameter_key)
);

CREATE INDEX IF NOT EXISTS idx_parameters_profile_id ON parameters(profile_id);

-- ------------------------------------------------------------
-- Measurements (recorded values)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS measurements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    parameter_key TEXT NOT NULL,
    -- Polymorphic value columns: only one populated based on parameter
    -- value_type. Validated at the application layer (the predefined
    -- parameters live in Python, so we cannot CHECK the type here).
    value_single DOUBLE PRECISION,
    value_double_1 DOUBLE PRECISION,
    value_double_2 DOUBLE PRECISION,
    value_text TEXT CHECK (value_text IS NULL OR length(value_text) <= 500),
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Optional link to the routine step that prompted this measurement.
    routine_id UUID REFERENCES routines(id) ON DELETE SET NULL,
    routine_step_id UUID REFERENCES routine_steps(id) ON DELETE SET NULL,
    note TEXT CHECK (note IS NULL OR length(note) <= 200),
    actor_user_id UUID,
    actor_device_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT measurement_has_value CHECK (
        value_single IS NOT NULL
        OR (value_double_1 IS NOT NULL AND value_double_2 IS NOT NULL)
        OR value_text IS NOT NULL
    )
);

CREATE INDEX IF NOT EXISTS idx_measurements_profile_param_date
    ON measurements(profile_id, parameter_key, recorded_at DESC);

-- ------------------------------------------------------------
-- RLS
-- ------------------------------------------------------------
ALTER TABLE parameters ENABLE ROW LEVEL SECURITY;
CREATE POLICY parameters_owner ON parameters FOR ALL USING (
    profile_id IN (SELECT id FROM profiles WHERE user_id = auth.uid())
);

ALTER TABLE measurements ENABLE ROW LEVEL SECURITY;
CREATE POLICY measurements_owner ON measurements FOR ALL USING (
    profile_id IN (SELECT id FROM profiles WHERE user_id = auth.uid())
);

-- ------------------------------------------------------------
-- updated_at trigger (parameters only — measurements are append-only)
-- ------------------------------------------------------------
CREATE TRIGGER parameters_updated_at BEFORE UPDATE ON parameters
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

COMMENT ON TABLE parameters IS
    'User-custom parameters. Predefined ones (glycemia, blood_pressure, weight, temperature, inr, oxygen_saturation, heart_rate) live in Python and are not persisted here.';
COMMENT ON COLUMN parameters.parameter_key IS
    'Unique key per profile — generated as ''custom:<uuid>'' on creation.';
COMMENT ON TABLE measurements IS
    'Recorded measurement values. Polymorphic by parameter value_type.';
