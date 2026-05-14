-- Migration 028: doctor extended fields (study, whatsapp, office hours, call preferences)
--
-- The iOS DoctorEditor surfaces several fields that the original schema
-- never modelled. Without a place to land them, the FastAPI layer rejects
-- the POST/PUT with 422 ("extra fields not permitted"), the iOS offline
-- queue discards the mutation, and on the next bootstrap refresh the local
-- doctor entry disappears — visible to the user as "the form doesn't save".
--
-- This migration adds those columns. They are all nullable free-text fields,
-- no backfill required.
--
--   * study                       — "Studio · Città" free description
--   * whatsapp_phone              — separate WhatsApp number (distinct from
--                                   the office phone used for chiama")
--   * whatsapp_message_template   — informal WhatsApp template (inline meds)
--   * office_hours                — plain-text office hours (the existing
--                                   schedule_json column is a structured
--                                   blob and unused by iOS)
--   * call_preferences            — free notes / preferences shown in the
--                                   "Richiedi ricetta · Chiama" sheet

ALTER TABLE doctors
    ADD COLUMN IF NOT EXISTS study TEXT,
    ADD COLUMN IF NOT EXISTS whatsapp_phone TEXT,
    ADD COLUMN IF NOT EXISTS whatsapp_message_template TEXT,
    ADD COLUMN IF NOT EXISTS office_hours TEXT,
    ADD COLUMN IF NOT EXISTS call_preferences TEXT;
