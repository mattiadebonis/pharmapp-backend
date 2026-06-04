-- 043_drop_notification_settings_columns.sql
-- Rimuove dalla tabella user_settings i campi configurabili dalla vecchia
-- pagina "Notifiche" del profilo iOS:
--   * notify_caregivers, notifications_enabled, refill_alerts_enabled
--     diventano comportamenti sempre attivi (notifiche dose e scorte non si
--     disattivano piu' globalmente; la capability caregiver e' rimossa).
--   * default_snooze_minutes e default_refill_threshold sono ora cablati a
--     livello app (10 min, 7 gg). I valori per-schedule (dosing_schedules.
--     snooze_minutes) e per-supply (supplies.refill_threshold_days) restano
--     editabili dalle rispettive UI di farmaco/scorta.

ALTER TABLE user_settings
    DROP COLUMN IF EXISTS notify_caregivers,
    DROP COLUMN IF EXISTS notifications_enabled,
    DROP COLUMN IF EXISTS refill_alerts_enabled,
    DROP COLUMN IF EXISTS default_snooze_minutes,
    DROP COLUMN IF EXISTS default_refill_threshold;
