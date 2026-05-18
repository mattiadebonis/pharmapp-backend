-- Migration 029: stock-MVP fields on medications and doctors
--
-- Aggiunge i campi necessari alla nuova vista "I miei farmaci" che
-- ricorda all'utente quando le scorte stanno per finire.
--
--   * medications.anticipo_reminder  — override per-farmaco dell'anticipo
--     reminder (giorni). Quando NULL, il client usa
--     UserSettings.defaultRefillThreshold (default 7).
--
--   * doctors.preferenza_canale      — canale di contatto preferito quando
--     i farmaci di questo medico vanno richiesti
--     ('telefono' | 'whatsapp' | 'email'). NULL = lascia che la UI scelga
--     in base ai contatti disponibili.
--
-- Tutti nullable, niente backfill richiesto. Il PharmaBaseModel ha
-- extra="forbid", quindi senza queste colonne il bootstrap del
-- nuovo iOS fallirebbe la validazione lato request.

ALTER TABLE medications
    ADD COLUMN IF NOT EXISTS anticipo_reminder INT;

ALTER TABLE doctors
    ADD COLUMN IF NOT EXISTS preferenza_canale TEXT
    CHECK (preferenza_canale IS NULL OR preferenza_canale IN ('telefono', 'whatsapp', 'email'));
