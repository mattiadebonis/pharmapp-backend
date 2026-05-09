-- Migration 027: iOS↔backend coverage gaps
--
-- 1. dose_events.injection_site — Today UI lets the user pick the rotation
--    site at confirmation time; we previously dropped it on the backend.
-- 2. medications.injection_sites_json — Setup wizard rotation cycle, used
--    server-side to compute the next site for therapy data reports.
-- 3. profiles.connection_status / relation_label — surfaces the managed
--    profile's invite state in bootstrap so the iOS UI does not have to
--    re-derive it locally on every launch.
-- 4. subscriptions — server-side StoreKit entitlement state, the source
--    of truth for paywall gating once the iOS PurchaseCoordinator forwards
--    its signed transactions to /v2/store/transactions/verify.

ALTER TABLE dose_events
    ADD COLUMN IF NOT EXISTS injection_site text;

ALTER TABLE medications
    ADD COLUMN IF NOT EXISTS injection_sites_json jsonb NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE profiles
    ADD COLUMN IF NOT EXISTS relation_label text,
    ADD COLUMN IF NOT EXISTS connection_status text
        CHECK (connection_status IN ('active', 'pending'));

CREATE TABLE IF NOT EXISTS subscriptions (
    user_id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    tier text NOT NULL DEFAULT 'free'
        CHECK (tier IN ('free', 'pro', 'family')),
    is_trial_active boolean NOT NULL DEFAULT false,
    expires_at timestamptz,
    last_validated_at timestamptz,
    original_transaction_id text UNIQUE,
    product_id text,
    environment text CHECK (environment IN ('sandbox', 'production')),
    raw_payload jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS subscriptions_original_transaction_idx
    ON subscriptions (original_transaction_id);

-- Lock the table down: only the service_role key (used by the FastAPI
-- backend) may read or write. The webhook + verify endpoint are server-
-- authoritative; clients never query this table directly.
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON subscriptions FROM anon, authenticated;
