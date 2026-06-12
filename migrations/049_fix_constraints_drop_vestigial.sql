-- =============================================================
-- Migration 049 — Fix CHECK troppo stretti + cycle_total_weeks + drop vestigiale
-- =============================================================
--
-- Bug fix (scoperti nel dead-code audit round 2):
--   1. dosing_schedules.format: il CHECK (mig 008) ammette solo 4 valori ma
--      l'enum iOS DoseFormat ne ha 12 e l'app invia rawValue raw
--      (AppModel.swift:2602) → selezionare "capsula"/"sciroppo"/… dava 422
--      (e violazione CHECK a livello DB). Allargato ai 12 valori iOS.
--   2. dosing_schedules.post_tapering_behavior: il CHECK ammetteva solo
--      fine_terapia/mantenimento ma iOS ha anche il case "ripeti". Aggiunto.
--   3. dosing_schedules.cycle_total_weeks: campo già decodificato da iOS
--      (Models.swift cycleTotalWeeks) ma mai persistito — la colonna non
--      esisteva. Aggiunta (con campo Pydantic + serializzazione iOS nello
--      stesso commit).
--
-- Dead schema:
--   - medications.anticipo_reminder (mig 029): zero referenze lato iOS e
--     zero logica backend. NB: la colonna NON risulta presente nel DB live
--     (la 029 non fu mai applicata in quella parte) — il DROP IF EXISTS è
--     idempotenza per ambienti dove esistesse. Rimosso anche il campo dai
--     Pydantic DTO nello stesso commit.
--
-- I Literal Pydantic (schemas/medication.py format e post_tapering_behavior,
-- schemas/dosing_schedule.py) sono allineati nello stesso commit.
-- Nomi constraint verificati su pg_constraint del DB live.
-- =============================================================

BEGIN;

-- 1. format: 4 → 12 valori (enum DoseFormat iOS completo)
ALTER TABLE dosing_schedules DROP CONSTRAINT IF EXISTS dosing_schedules_format_check;
ALTER TABLE dosing_schedules ADD CONSTRAINT dosing_schedules_format_check
    CHECK (format IN ('compressa','capsula','granuli','gocce','sciroppo','iniettabile',
                      'inalatore','cerotto','collirio','crema','supposta','altro'));

-- 2. post_tapering_behavior: + 'ripeti' (case iOS PostTaperingBehavior.ripeti)
ALTER TABLE dosing_schedules DROP CONSTRAINT IF EXISTS dosing_schedules_post_tapering_behavior_check;
ALTER TABLE dosing_schedules ADD CONSTRAINT dosing_schedules_post_tapering_behavior_check
    CHECK (post_tapering_behavior IN ('fine_terapia','ripeti','mantenimento'));

COMMENT ON COLUMN dosing_schedules.post_tapering_behavior IS
    'Behaviour after the final "A step" phase completes: fine_terapia deactivates the medication; ripeti restarts the phase sequence; mantenimento keeps the last step dose as a fixed continuation.';

-- 3. cycle_total_weeks: persiste il campo iOS cycleTotalWeeks (es. cicli iniettabili)
ALTER TABLE dosing_schedules ADD COLUMN IF NOT EXISTS cycle_total_weeks INT;

COMMENT ON COLUMN dosing_schedules.cycle_total_weeks IS
    'Durata totale del ciclo in settimane (es. rotazione siti iniezione). Scritto da iOS, pass-through.';

-- 4. Dead column (idempotenza: assente nel DB live)
ALTER TABLE medications DROP COLUMN IF EXISTS anticipo_reminder;

COMMIT;
