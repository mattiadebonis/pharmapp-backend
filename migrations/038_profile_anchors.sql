-- Migration 038: "La mia giornata" anchors per profilo.
--
-- Aggiunge la colonna `profiles.anchors` (JSONB) per memorizzare i 5
-- "momenti della giornata" personali (Risveglio, Colazione, Pranzo,
-- Cena, Notte). Ogni anchor ha:
--   * kind          — 'wake' | 'breakfast' | 'lunch' | 'dinner' | 'night'
--   * weekday_time  — "HH:mm" (24h, Italian timezone implicit) — usato
--                     tutti i giorni quando `weekend_time` è null
--   * weekend_time  — "HH:mm" o null. Quando presente, gli orari di
--                     sabato/domenica usano questo valore invece di
--                     `weekday_time`.
--
-- Il default copre i 5 anchor con orari "tipici" italiani in single-time
-- mode (nessuno split weekend). Backfill automatico: il `NOT NULL DEFAULT`
-- popola tutte le righe esistenti.
--
-- PharmaBaseModel ha extra="forbid", quindi questa colonna deve esistere
-- prima che la nuova versione del client la invii nel payload.

ALTER TABLE profiles
    ADD COLUMN IF NOT EXISTS anchors JSONB NOT NULL DEFAULT '[
        {"kind":"wake","weekday_time":"06:30"},
        {"kind":"breakfast","weekday_time":"07:00"},
        {"kind":"lunch","weekday_time":"13:00"},
        {"kind":"dinner","weekday_time":"20:00"},
        {"kind":"night","weekday_time":"23:00"}
    ]'::jsonb;
