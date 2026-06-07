-- 044_dosing_schedule_strength.sql
-- Persiste il dosaggio (strength) per unità scelto in Posologia.
-- Il dosaggio non è più scelto nello Step 1 del wizard iOS ("Il farmaco"),
-- ma in Posologia tramite uno stepper che scorre i dosaggi AIFA disponibili
-- (es. 5 / 10 / 20 mg). La dose totale di un'assunzione =
--   pills_per_dose (numero di unità) × strength_mg (mg per unità).
--
-- strength_mg   : valore numerico in mg per singola unità (compressa, ...).
--                 NULL per le forme che non esprimono una dose discreta per
--                 unità (es. gocce con concentrazione mg/ml).
-- strength_text : testo grezzo del dosaggio dal registro AIFA (es. "0,5 mg"),
--                 conservato per display fedele.

ALTER TABLE dosing_schedules
    ADD COLUMN IF NOT EXISTS strength_mg numeric,
    ADD COLUMN IF NOT EXISTS strength_text text;

-- Regola di coerenza: il dosaggio in mg, se presente, non può essere negativo.
ALTER TABLE dosing_schedules
    DROP CONSTRAINT IF EXISTS dosing_schedules_strength_mg_non_negative;
ALTER TABLE dosing_schedules
    ADD CONSTRAINT dosing_schedules_strength_mg_non_negative
    CHECK (strength_mg IS NULL OR strength_mg >= 0);
