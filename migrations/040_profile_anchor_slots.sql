-- Migration 040: refactor `profiles.anchors` da
-- {kind, time, weekdays[]} (single time per anchor) a
-- {kind, slots:[{id, time, weekdays[]}]} (multi-slot per anchor).
--
-- Motivazione: un solo orario per anchor non scalava per pattern come
-- turni di lavoro (Lun-Mer 06:00 / Gio-Ven 14:00 / Sab-Dom 09:00) o
-- weekend con orario distinto. Il modello a slot multipli copre tutti
-- questi casi: ogni slot è un (orario + giorni in cui si applica), e il
-- vincolo "ogni giorno appartiene a un solo slot" viene gestito
-- lato client al momento della modifica.
--
-- Backwards compat: la migration è destructive (drop + re-add) — i 5
-- anchor di default vengono ripopolati con UN solo slot ciascuno su
-- tutti i 7 giorni. Su produzione (ancora non deployato) nessun dato
-- utente viene perso.

ALTER TABLE profiles DROP COLUMN IF EXISTS anchors;

ALTER TABLE profiles
    ADD COLUMN anchors JSONB NOT NULL DEFAULT '[
        {"kind":"wake",      "slots":[{"id":"00000000-0000-0000-0000-000000000001","time":"06:30","weekdays":[1,2,3,4,5,6,7]}]},
        {"kind":"breakfast", "slots":[{"id":"00000000-0000-0000-0000-000000000002","time":"07:00","weekdays":[1,2,3,4,5,6,7]}]},
        {"kind":"lunch",     "slots":[{"id":"00000000-0000-0000-0000-000000000003","time":"13:00","weekdays":[1,2,3,4,5,6,7]}]},
        {"kind":"dinner",    "slots":[{"id":"00000000-0000-0000-0000-000000000004","time":"20:00","weekdays":[1,2,3,4,5,6,7]}]},
        {"kind":"night",     "slots":[{"id":"00000000-0000-0000-0000-000000000005","time":"23:00","weekdays":[1,2,3,4,5,6,7]}]}
    ]'::jsonb;
