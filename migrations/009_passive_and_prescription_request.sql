-- Migration 009: passive dose auto-registration + prescription renewal requests.
--
-- dose_events:
--   * auto_registered_at  → timestamp at which the backend/client created a
--                            "taken" event automatically for a passive dose.
--                            NULL for user-confirmed active doses.
--   * user_corrected_at   → timestamp at which the user corrected the time of
--                            an auto-registered passive dose. NULL if the user
--                            accepted the auto-registered time as-is.
--
-- prescriptions:
--   * requested_at        → timestamp at which the user last pressed
--                            "Chiedi ricetta" on this prescription.
--   * request_status      → tracks the renewal-request lifecycle:
--                            'received'  default (prescription in hand),
--                            'requested' (user asked the doctor, waiting),
--                            'expired'   (request gave up / prescription lapsed).
--
-- All new columns are nullable / defaulted so existing rows stay valid.

ALTER TABLE dose_events
    ADD COLUMN IF NOT EXISTS auto_registered_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS user_corrected_at TIMESTAMPTZ;

COMMENT ON COLUMN dose_events.auto_registered_at IS
    'Set when the dose event was created automatically for a passive medication. NULL for user-confirmed events.';
COMMENT ON COLUMN dose_events.user_corrected_at IS
    'Set when the user corrects the taken_at of a previously auto-registered passive dose.';

ALTER TABLE prescriptions
    ADD COLUMN IF NOT EXISTS requested_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS request_status TEXT NOT NULL DEFAULT 'received'
        CHECK (request_status IN ('received', 'requested', 'expired'));

COMMENT ON COLUMN prescriptions.requested_at IS
    'Timestamp of the most recent "Chiedi ricetta" action. NULL if never requested.';
COMMENT ON COLUMN prescriptions.request_status IS
    'Lifecycle of a prescription renewal request: received (in hand), requested (waiting), expired.';
