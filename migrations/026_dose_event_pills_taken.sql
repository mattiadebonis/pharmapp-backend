-- Aggiunge `pills_taken` opzionale a `dose_events` per supportare le
-- dosi parziali (es. mezza compressa, dose ridotta su consiglio medico).
-- Permette di derivare lo stato "parziale" (verde chiaro nei grafici)
-- confrontando con `dosing_schedules.pills_per_dose` al momento del
-- calcolo dell'aderenza.
--
-- Backwards compatible: NULL di default. NULL viene trattato come full
-- intake (== pills_per_dose) dal service di aggregazione.

ALTER TABLE dose_events
    ADD COLUMN IF NOT EXISTS pills_taken DOUBLE PRECISION
        CHECK (pills_taken IS NULL OR pills_taken >= 0);

COMMENT ON COLUMN dose_events.pills_taken IS
    'Dose effettivamente assunta (può differire da dosing_schedules.pills_per_dose '
    'per dosi parziali). NULL → trattato come full intake.';
