-- Migration 002: Add weekly_overrides to dosing_schedules
-- Supports per-weekday dose variation (e.g. Warfarin variable dosing).
-- Keys are Calendar weekday strings "1"–"7" (1=Sun, 2=Mon, … 7=Sat).
-- A value of 0 means skip that day (no event, no notification generated).

ALTER TABLE dosing_schedules
    ADD COLUMN IF NOT EXISTS weekly_overrides JSONB DEFAULT NULL;

COMMENT ON COLUMN dosing_schedules.weekly_overrides IS
    'Optional per-weekday dose override. Keys are Calendar weekday strings '
    '"1"–"7" (1=Sun, 2=Mon, 3=Tue, 4=Wed, 5=Thu, 6=Fri, 7=Sat). '
    'Values are pills_per_dose for that day. 0 = skip day entirely.';
