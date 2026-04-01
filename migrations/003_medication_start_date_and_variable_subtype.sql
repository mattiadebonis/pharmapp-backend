-- Migration 003: add start_date to medications and variable_subtype to dosing_schedules

ALTER TABLE medications
    ADD COLUMN IF NOT EXISTS start_date DATE DEFAULT CURRENT_DATE;

UPDATE medications
SET start_date = COALESCE(
    (
        SELECT s.purchase_date
        FROM supplies s
        WHERE s.medication_id = medications.id
        ORDER BY s.created_at ASC
        LIMIT 1
    ),
    CURRENT_DATE
)
WHERE start_date IS NULL;

ALTER TABLE medications
    ALTER COLUMN start_date SET NOT NULL;

COMMENT ON COLUMN medications.start_date IS
    'Therapy start date shown in medication overview and used by variable/tapering schedules.';

ALTER TABLE dosing_schedules
    ADD COLUMN IF NOT EXISTS variable_subtype TEXT DEFAULT NULL
        CHECK (variable_subtype IN ('weekly', 'tapering', 'escalation'));

UPDATE dosing_schedules
SET variable_subtype = CASE
    WHEN weekly_overrides IS NOT NULL THEN 'weekly'
    WHEN schedule_type = 'tapering' THEN 'tapering'
    ELSE variable_subtype
END
WHERE variable_subtype IS NULL;

COMMENT ON COLUMN dosing_schedules.variable_subtype IS
    'Subtype for variable schedules. Keeps legacy schedule_type=tapering compatible while distinguishing weekly, tapering, escalation.';
