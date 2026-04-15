-- Migration 008: add per-mode fields for the redesigned "Quando lo prendi" scheduler.
--
-- Adds:
--   * format / daily_limit / weekly_alert_threshold → "Al bisogno" mode
--   * cycle_pattern / cycle_weekdays / notify_day_before → "Ciclo" mode
--   * times[].preposto is now documented (optional meal context string)
--
-- Existing schedule_type / variable_subtype stay unchanged: the 3 PRO modes
-- (Per giorno / Scalare ↓ / Crescente ↑) continue to map to
-- schedule_type='tapering' + variable_subtype ∈ ('weekly','tapering','escalation').

ALTER TABLE dosing_schedules
    ADD COLUMN IF NOT EXISTS format TEXT
        CHECK (format IN ('compressa', 'inalatore', 'gocce', 'altro')),
    ADD COLUMN IF NOT EXISTS daily_limit INT,
    ADD COLUMN IF NOT EXISTS weekly_alert_threshold INT,
    ADD COLUMN IF NOT EXISTS cycle_pattern TEXT
        CHECK (cycle_pattern IN ('weekly', 'biweekly', 'every_n')),
    ADD COLUMN IF NOT EXISTS cycle_weekdays INT[],
    ADD COLUMN IF NOT EXISTS notify_day_before BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS post_tapering_behavior TEXT
        CHECK (post_tapering_behavior IN ('fine_terapia', 'mantenimento'));

COMMENT ON COLUMN dosing_schedules.format IS
    'Dose format for as-needed schedules: compressa, inalatore (puff), gocce (gtt), altro. Drives UI unit label.';
COMMENT ON COLUMN dosing_schedules.daily_limit IS
    'Optional "Massimo al giorno" counter for as-needed schedules.';
COMMENT ON COLUMN dosing_schedules.weekly_alert_threshold IS
    'Threshold for "Alert settimanale >Nx/sett" on as-needed schedules. NULL disables the alert.';
COMMENT ON COLUMN dosing_schedules.cycle_pattern IS
    'Cycle repetition pattern: weekly, biweekly, every_n. Used with cycle_weekdays and cycle_days.';
COMMENT ON COLUMN dosing_schedules.cycle_weekdays IS
    'Selected weekdays for cycle schedules (ISO: 1=Mon … 7=Sun).';
COMMENT ON COLUMN dosing_schedules.notify_day_before IS
    'When true, the app also notifies the day before each cycle event ("Avvisa il giorno prima").';
COMMENT ON COLUMN dosing_schedules.post_tapering_behavior IS
    'Behaviour after the final "A step" phase completes: fine_terapia deactivates the medication; mantenimento keeps the last step dose as a fixed continuation.';

-- The times JSONB payload may now include an optional "preposto" field
-- (meal context string). Existing rows without it remain valid.
COMMENT ON COLUMN dosing_schedules.times IS
    'List of intake times. Each element: {"time": "HH:MM", "label": string?, "preposto": string?}.';
