-- Migration 041: aggiungere colonna `doctors.secretary_office_hours TEXT`.
--
-- Motivazione: il modello `doctors` già esponeva contatti della segreteria
-- (`secretary_name`, `secretary_email`, `secretary_phone`,
-- `secretary_schedule_json`) ma mancava il campo testuale libero per gli
-- orari segreteria, equivalente a `office_hours` per il medico stesso.
-- Mantenere coerenza col pattern free-text esistente evita di forzare il
-- client iOS a serializzare un JSONB envelope per una singola riga di
-- testo "Lun-Ven 9-17".

ALTER TABLE doctors ADD COLUMN IF NOT EXISTS secretary_office_hours TEXT;
