-- Migration 030: campi Today v2 per criticality, pausa terapia,
-- modalità ridotta e sospensione clinica.
--
--   * medications.criticality              — 'none' | 'critical'. Drive badge
--     rosso "Critico" sulla card Today (Tacrolimus, anticoagulanti,
--     oncologici). Default 'none' per retrocompatibilità.
--
--   * medications.suspended_by_doctor_at   — timestamp di sospensione
--     clinica decisa dal medico. Diverso da `is_paused` (utente).
--     Drive il banner "ⓘ Sospesa dal medico · N farmaci in pausa".
--
--   * profiles.therapy_paused_at           — timestamp set quando l'utente
--     mette in pausa la terapia globale. Drive lo stato `0.3 Pausa` che
--     sostituisce la timeline con una sola card muted "In pausa dal X".
--
--   * profiles.critical_only_mode          — boolean per "Modalità ridotta /
--     Giornata difficile". Quando true, la Today filtra solo i farmaci con
--     criticality='critical'. Drive lo stato `6.1 Giornata difficile`.
--
-- Tutti nullable o con default → niente backfill. PharmaBaseModel ha
-- extra="forbid", quindi le colonne devono esistere quando il bootstrap
-- ritorna profilo/farmaco.

ALTER TABLE medications
    ADD COLUMN IF NOT EXISTS criticality TEXT
    CHECK (criticality IS NULL OR criticality IN ('none', 'critical'))
    DEFAULT 'none';

ALTER TABLE medications
    ADD COLUMN IF NOT EXISTS suspended_by_doctor_at TIMESTAMPTZ;

ALTER TABLE profiles
    ADD COLUMN IF NOT EXISTS therapy_paused_at TIMESTAMPTZ;

ALTER TABLE profiles
    ADD COLUMN IF NOT EXISTS critical_only_mode BOOLEAN NOT NULL DEFAULT false;
