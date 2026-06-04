-- 042_alarm_notification_default.sql
-- Promuove la modalita' "alarm" (sveglia con suono critico, ripetuta) a default
-- per le notifiche delle dosi farmaco. Le schedule esistenti con valore 'normal'
-- vengono backfillate a 'alarm' per coerenza col nuovo comportamento di prodotto.
-- L'utente puo' sempre tornare a 'normal' per singolo farmaco dalle impostazioni.

ALTER TABLE dosing_schedules
    ALTER COLUMN notification_level SET DEFAULT 'alarm';

UPDATE dosing_schedules
SET notification_level = 'alarm',
    updated_at = now()
WHERE notification_level = 'normal';
