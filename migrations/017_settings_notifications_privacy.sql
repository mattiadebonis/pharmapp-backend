-- Estende `user_settings` con i toggle del Profilo (sezioni Notifiche e
-- Privacy/Dati) precedentemente trattenuti solo nel client iOS.
-- Tutti i campi sono booleani con default sicuri, retro-compatibili.
--
-- Sezione Notifiche:
--   - notifications_enabled: master switch promemoria dosi
--   - refill_alerts_enabled: avvisi scorte basse
--
-- Sezione Privacy / Dati:
--   - biometrics_enabled: Face ID / Touch ID per aprire l'app
--   - face_id_sensitive_actions: Face ID per azioni sensibili
--     (export PDF, gestione medici, eliminazione dati)
--   - anonymous_notifications: notifiche senza nome farmaco/dose
--   - hide_medication_names: pallini colore al posto dei nomi nelle UI
--     pubbliche (cabinet, today, widget)

ALTER TABLE user_settings
    ADD COLUMN IF NOT EXISTS notifications_enabled BOOLEAN NOT NULL DEFAULT true,
    ADD COLUMN IF NOT EXISTS refill_alerts_enabled BOOLEAN NOT NULL DEFAULT true,
    ADD COLUMN IF NOT EXISTS biometrics_enabled BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS face_id_sensitive_actions BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS anonymous_notifications BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS hide_medication_names BOOLEAN NOT NULL DEFAULT false;
