-- ============================================================
-- Migration 010: prescription_requests (supply-reminder history)
-- ============================================================
-- Introduce a dedicated table to track the lifecycle of each
-- "Chiedi ricetta" user action as an independent record, so the
-- app can render a full request history instead of overwriting
-- a single `prescriptions.request_status` field.
--
-- Also adds a denormalised `medications.prescribing_doctor_id`
-- pointer that lets the client pre-fill the doctor picker of the
-- new PrescriptionRequestSheet without walking the (legacy)
-- prescriptions table.
--
-- Legacy `prescriptions.requested_at / request_status` columns
-- are kept as-is for backward compatibility — migration 011+ may
-- eventually drop them once all clients are on the new schema.
-- A one-shot seed below migrates any currently-pending record
-- (request_status='requested') into a PrescriptionRequest with
-- status='pending' so no in-flight request is lost at cutover.
-- ============================================================


-- ------------------------------------------------------------
-- 1) medications.prescribing_doctor_id
-- ------------------------------------------------------------
ALTER TABLE medications
    ADD COLUMN IF NOT EXISTS prescribing_doctor_id UUID
        REFERENCES doctors(id) ON DELETE SET NULL;

COMMENT ON COLUMN medications.prescribing_doctor_id IS
    'Default doctor pre-selected in the "Chiedi ricetta" sheet. NULL means the user must pick one the first time.';

CREATE INDEX IF NOT EXISTS idx_medications_prescribing_doctor_id
    ON medications (prescribing_doctor_id)
    WHERE prescribing_doctor_id IS NOT NULL;


-- ------------------------------------------------------------
-- 2) prescription_requests table
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS prescription_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    medication_id UUID NOT NULL REFERENCES medications(id) ON DELETE CASCADE,
    doctor_id UUID REFERENCES doctors(id) ON DELETE SET NULL,
    sent_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    channel TEXT NOT NULL
        CHECK (channel IN ('whatsapp', 'mail', 'copy')),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'purchased', 'cancelled')),
    purchased_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE prescription_requests IS
    'Append-only log of "Chiedi ricetta" user actions. One row per request; status transitions pending -> purchased | cancelled.';

CREATE INDEX IF NOT EXISTS idx_prescription_requests_medication_id
    ON prescription_requests (medication_id);

CREATE INDEX IF NOT EXISTS idx_prescription_requests_status
    ON prescription_requests (status)
    WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS idx_prescription_requests_sent_at
    ON prescription_requests (sent_at DESC);


-- ------------------------------------------------------------
-- 3) RLS — access via the medication -> profile -> user chain
-- ------------------------------------------------------------
ALTER TABLE prescription_requests ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS prescription_requests_owner ON prescription_requests;
CREATE POLICY prescription_requests_owner ON prescription_requests FOR ALL USING (
    medication_id IN (
        SELECT m.id FROM medications m
        JOIN profiles p ON p.id = m.profile_id
        WHERE p.user_id = auth.uid()
    )
);


-- ------------------------------------------------------------
-- 4) updated_at trigger
-- ------------------------------------------------------------
DROP TRIGGER IF EXISTS prescription_requests_updated_at ON prescription_requests;
CREATE TRIGGER prescription_requests_updated_at
    BEFORE UPDATE ON prescription_requests
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();


-- ------------------------------------------------------------
-- 5) Seed legacy pending requests
-- ------------------------------------------------------------
-- Convert every prescription currently flagged as request_status='requested'
-- (migration 009) into a new prescription_requests row with channel='mail'
-- (most common default for legacy flows) and status='pending'. Idempotent:
-- we only insert rows that have no matching prescription_requests row with
-- the same sent_at timestamp for that medication yet.
INSERT INTO prescription_requests (medication_id, doctor_id, sent_at, channel, status)
SELECT
    p.medication_id,
    p.doctor_id,
    p.requested_at,
    'mail',
    'pending'
FROM prescriptions p
WHERE p.request_status = 'requested'
  AND p.requested_at IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM prescription_requests pr
      WHERE pr.medication_id = p.medication_id
        AND pr.sent_at = p.requested_at
  );
