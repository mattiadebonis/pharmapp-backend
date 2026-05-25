-- Migration 039: refactor `profiles.anchors` da
-- {kind, weekday_time, weekend_time?} a {kind, time, weekdays[]}.
--
-- Motivazione: il modello weekday/weekend non scalava per pattern come
-- turni di lavoro o weekend skip ("niente pranzo sabato"). Ora ogni
-- anchor ha:
--   * time      — "HH:mm" unico
--   * weekdays  — array di interi 1-7 (ISO 8601: 1=Lun … 7=Dom)
--
-- La migration è destructive su dev (drop + re-add) perché 038 è appena
-- stata aggiunta e nessun dato di produzione ha valore: re-applicarla
-- ripopola la colonna con i 5 anchor di default su tutti i 7 giorni.

ALTER TABLE profiles DROP COLUMN IF EXISTS anchors;

ALTER TABLE profiles
    ADD COLUMN anchors JSONB NOT NULL DEFAULT '[
        {"kind":"wake","time":"06:30","weekdays":[1,2,3,4,5,6,7]},
        {"kind":"breakfast","time":"07:00","weekdays":[1,2,3,4,5,6,7]},
        {"kind":"lunch","time":"13:00","weekdays":[1,2,3,4,5,6,7]},
        {"kind":"dinner","time":"20:00","weekdays":[1,2,3,4,5,6,7]},
        {"kind":"night","time":"23:00","weekdays":[1,2,3,4,5,6,7]}
    ]'::jsonb;
