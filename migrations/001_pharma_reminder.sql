-- ============================================================
-- Pharma Reminder — New Schema
-- Migration 001: Complete schema for the new data model
-- ============================================================

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- PROFILES
-- ============================================================
CREATE TABLE IF NOT EXISTS profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    profile_type TEXT NOT NULL DEFAULT 'own' CHECK (profile_type IN ('own', 'assisted', 'dependent')),
    display_name TEXT NOT NULL,
    birth_date DATE,
    color TEXT,
    emoji TEXT,
    parent_user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_profiles_user_id ON profiles(user_id);
CREATE INDEX idx_profiles_parent_user_id ON profiles(parent_user_id) WHERE parent_user_id IS NOT NULL;

-- ============================================================
-- DOCTORS
-- ============================================================
CREATE TABLE IF NOT EXISTS doctors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    surname TEXT,
    specialization TEXT,
    email TEXT,
    phone TEXT,
    address TEXT,
    schedule_json JSONB,
    secretary_name TEXT,
    secretary_email TEXT,
    secretary_phone TEXT,
    secretary_schedule_json JSONB,
    prescription_message_template TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_doctors_user_id ON doctors(user_id);

-- ============================================================
-- MEDICATIONS
-- ============================================================
CREATE TABLE IF NOT EXISTS medications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    catalog_product_key TEXT,
    catalog_country TEXT,
    name TEXT NOT NULL,
    principle TEXT,
    color TEXT,
    category TEXT DEFAULT 'farmaco' CHECK (category IN ('farmaco', 'otc', 'integratore')),
    tracking_mode TEXT NOT NULL DEFAULT 'passive' CHECK (tracking_mode IN ('passive', 'active')),
    requires_prescription BOOLEAN NOT NULL DEFAULT false,
    is_paused BOOLEAN NOT NULL DEFAULT false,
    is_archived BOOLEAN NOT NULL DEFAULT false,
    shared_with_caregiver BOOLEAN NOT NULL DEFAULT false,
    image_url TEXT,
    notes TEXT,
    catalog_snapshot JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_medications_profile_id ON medications(profile_id);
CREATE INDEX idx_medications_is_paused ON medications(profile_id) WHERE is_paused = false AND is_archived = false;

-- ============================================================
-- DOSING SCHEDULES
-- ============================================================
CREATE TABLE IF NOT EXISTS dosing_schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    medication_id UUID NOT NULL REFERENCES medications(id) ON DELETE CASCADE,
    schedule_type TEXT NOT NULL DEFAULT 'scheduled'
        CHECK (schedule_type IN ('scheduled', 'as_needed', 'cycle', 'tapering')),
    -- Common fields
    times JSONB NOT NULL DEFAULT '[]',  -- [{time: "08:00", label: "Mattina"}, ...]
    pills_per_dose DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    -- as_needed fields
    max_per_day INTEGER,
    min_interval_hours INTEGER,
    condition TEXT,
    -- cycle fields (antibiotics)
    cycle_days INTEGER,
    cycle_start_date DATE,
    -- tapering fields (cortisone)
    tapering_steps JSONB,  -- [{from_day: 1, to_day: 3, dose: 25}, ...]
    -- rrule for complex recurrence
    rrule TEXT,
    -- status
    is_active BOOLEAN NOT NULL DEFAULT true,
    importance TEXT NOT NULL DEFAULT 'standard'
        CHECK (importance IN ('vital', 'essential', 'standard')),
    notification_level TEXT NOT NULL DEFAULT 'normal'
        CHECK (notification_level IN ('normal', 'alarm')),
    snooze_minutes INTEGER NOT NULL DEFAULT 10,
    notifications_silenced BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_dosing_schedules_medication_id ON dosing_schedules(medication_id);
CREATE INDEX idx_dosing_schedules_active ON dosing_schedules(medication_id) WHERE is_active = true;

-- ============================================================
-- SUPPLIES (Stock/Inventory)
-- ============================================================
CREATE TABLE IF NOT EXISTS supplies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    medication_id UUID NOT NULL REFERENCES medications(id) ON DELETE CASCADE,
    pills_at_purchase DOUBLE PRECISION NOT NULL,
    current_pills DOUBLE PRECISION NOT NULL,
    purchase_date DATE NOT NULL DEFAULT CURRENT_DATE,
    refill_threshold_days INTEGER NOT NULL DEFAULT 7,
    package_units INTEGER,
    package_label TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- One supply per medication (latest purchase)
CREATE UNIQUE INDEX idx_supplies_medication_id ON supplies(medication_id);

-- ============================================================
-- PRESCRIPTIONS
-- ============================================================
CREATE TABLE IF NOT EXISTS prescriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    medication_id UUID NOT NULL REFERENCES medications(id) ON DELETE CASCADE,
    doctor_id UUID REFERENCES doctors(id) ON DELETE SET NULL,
    prescription_type TEXT NOT NULL DEFAULT 'ricetta_rossa'
        CHECK (prescription_type IN ('ricetta_rossa', 'ricetta_bianca', 'specialist')),
    issued_date DATE NOT NULL,
    expiry_date DATE NOT NULL,
    total_packages INTEGER NOT NULL DEFAULT 1,
    remaining_packages INTEGER NOT NULL DEFAULT 1,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_prescriptions_medication_id ON prescriptions(medication_id);
CREATE INDEX idx_prescriptions_expiry ON prescriptions(expiry_date) WHERE remaining_packages > 0;

-- ============================================================
-- DOSE EVENTS
-- ============================================================
CREATE TABLE IF NOT EXISTS dose_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    medication_id UUID NOT NULL REFERENCES medications(id) ON DELETE CASCADE,
    dosing_schedule_id UUID REFERENCES dosing_schedules(id) ON DELETE SET NULL,
    profile_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    due_at TIMESTAMPTZ NOT NULL,
    taken_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'taken', 'missed', 'skipped', 'snoozed')),
    snooze_count INTEGER NOT NULL DEFAULT 0,
    actor_user_id UUID,
    actor_device_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_dose_events_medication_id ON dose_events(medication_id);
CREATE INDEX idx_dose_events_profile_date ON dose_events(profile_id, due_at DESC);
CREATE INDEX idx_dose_events_status ON dose_events(medication_id, status) WHERE status = 'pending';

-- ============================================================
-- CAREGIVER RELATIONS
-- ============================================================
CREATE TABLE IF NOT EXISTS caregiver_relations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    caregiver_user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    invite_code TEXT UNIQUE NOT NULL,
    invite_expires_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'patient_confirmation', 'active', 'rejected', 'revoked')),
    permissions JSONB NOT NULL DEFAULT '["view_medications", "view_adherence_history", "receive_low_stock_notifications"]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_caregiver_patient ON caregiver_relations(patient_user_id) WHERE status = 'active';
CREATE INDEX idx_caregiver_caregiver ON caregiver_relations(caregiver_user_id) WHERE status = 'active';
CREATE UNIQUE INDEX idx_caregiver_invite_code ON caregiver_relations(invite_code) WHERE status IN ('pending', 'patient_confirmation');

-- ============================================================
-- PENDING CHANGES (Caregiver approval flow)
-- ============================================================
CREATE TABLE IF NOT EXISTS pending_changes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    caregiver_relation_id UUID NOT NULL REFERENCES caregiver_relations(id) ON DELETE CASCADE,
    medication_id UUID NOT NULL REFERENCES medications(id) ON DELETE CASCADE,
    change_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected')),
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_pending_changes_status ON pending_changes(caregiver_relation_id) WHERE status = 'pending';

-- ============================================================
-- ACTIVITY LOGS
-- ============================================================
CREATE TABLE IF NOT EXISTS activity_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    profile_id UUID REFERENCES profiles(id) ON DELETE SET NULL,
    medication_id UUID REFERENCES medications(id) ON DELETE SET NULL,
    action_type TEXT NOT NULL,
    details JSONB,
    actor_user_id UUID,
    actor_device_id TEXT,
    source TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_activity_logs_user_date ON activity_logs(user_id, created_at DESC);
CREATE INDEX idx_activity_logs_medication ON activity_logs(medication_id) WHERE medication_id IS NOT NULL;

-- ============================================================
-- DEVICE TOKENS (Push notifications)
-- ============================================================
CREATE TABLE IF NOT EXISTS device_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    token TEXT UNIQUE NOT NULL,
    platform TEXT NOT NULL CHECK (platform IN ('ios', 'android')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_device_tokens_user_id ON device_tokens(user_id);

-- ============================================================
-- USER SETTINGS
-- ============================================================
CREATE TABLE IF NOT EXISTS user_settings (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    catalog_country TEXT NOT NULL DEFAULT 'it',
    default_refill_threshold INTEGER NOT NULL DEFAULT 7,
    default_tracking_mode TEXT NOT NULL DEFAULT 'passive'
        CHECK (default_tracking_mode IN ('passive', 'active')),
    default_snooze_minutes INTEGER NOT NULL DEFAULT 10,
    grace_minutes INTEGER NOT NULL DEFAULT 120,
    notify_caregivers BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- ROW LEVEL SECURITY POLICIES
-- ============================================================

-- Profiles: users can only see their own profiles or profiles they manage as caregiver
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
CREATE POLICY profiles_owner ON profiles FOR ALL USING (user_id = auth.uid());

-- Medications: access through profile ownership
ALTER TABLE medications ENABLE ROW LEVEL SECURITY;
CREATE POLICY medications_owner ON medications FOR ALL USING (
    profile_id IN (SELECT id FROM profiles WHERE user_id = auth.uid())
);

-- Dosing schedules: access through medication -> profile ownership
ALTER TABLE dosing_schedules ENABLE ROW LEVEL SECURITY;
CREATE POLICY dosing_schedules_owner ON dosing_schedules FOR ALL USING (
    medication_id IN (
        SELECT m.id FROM medications m
        JOIN profiles p ON p.id = m.profile_id
        WHERE p.user_id = auth.uid()
    )
);

-- Supplies: access through medication
ALTER TABLE supplies ENABLE ROW LEVEL SECURITY;
CREATE POLICY supplies_owner ON supplies FOR ALL USING (
    medication_id IN (
        SELECT m.id FROM medications m
        JOIN profiles p ON p.id = m.profile_id
        WHERE p.user_id = auth.uid()
    )
);

-- Prescriptions: access through medication
ALTER TABLE prescriptions ENABLE ROW LEVEL SECURITY;
CREATE POLICY prescriptions_owner ON prescriptions FOR ALL USING (
    medication_id IN (
        SELECT m.id FROM medications m
        JOIN profiles p ON p.id = m.profile_id
        WHERE p.user_id = auth.uid()
    )
);

-- Doctors: users can only see their own doctors
ALTER TABLE doctors ENABLE ROW LEVEL SECURITY;
CREATE POLICY doctors_owner ON doctors FOR ALL USING (user_id = auth.uid());

-- Dose events: access through profile
ALTER TABLE dose_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY dose_events_owner ON dose_events FOR ALL USING (
    profile_id IN (SELECT id FROM profiles WHERE user_id = auth.uid())
);

-- Caregiver relations: either patient or caregiver can see
ALTER TABLE caregiver_relations ENABLE ROW LEVEL SECURITY;
CREATE POLICY caregiver_relations_access ON caregiver_relations FOR ALL USING (
    patient_user_id = auth.uid() OR caregiver_user_id = auth.uid()
);

-- Pending changes: through caregiver relation
ALTER TABLE pending_changes ENABLE ROW LEVEL SECURITY;
CREATE POLICY pending_changes_access ON pending_changes FOR ALL USING (
    caregiver_relation_id IN (
        SELECT id FROM caregiver_relations
        WHERE patient_user_id = auth.uid() OR caregiver_user_id = auth.uid()
    )
);

-- Activity logs: users can only see their own logs
ALTER TABLE activity_logs ENABLE ROW LEVEL SECURITY;
CREATE POLICY activity_logs_owner ON activity_logs FOR ALL USING (user_id = auth.uid());

-- Device tokens: users can only manage their own tokens
ALTER TABLE device_tokens ENABLE ROW LEVEL SECURITY;
CREATE POLICY device_tokens_owner ON device_tokens FOR ALL USING (user_id = auth.uid());

-- User settings: users can only see/edit their own settings
ALTER TABLE user_settings ENABLE ROW LEVEL SECURITY;
CREATE POLICY user_settings_owner ON user_settings FOR ALL USING (user_id = auth.uid());

-- ============================================================
-- UPDATED_AT TRIGGER
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER profiles_updated_at BEFORE UPDATE ON profiles FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER medications_updated_at BEFORE UPDATE ON medications FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER dosing_schedules_updated_at BEFORE UPDATE ON dosing_schedules FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER supplies_updated_at BEFORE UPDATE ON supplies FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER prescriptions_updated_at BEFORE UPDATE ON prescriptions FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER doctors_updated_at BEFORE UPDATE ON doctors FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER dose_events_updated_at BEFORE UPDATE ON dose_events FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER caregiver_relations_updated_at BEFORE UPDATE ON caregiver_relations FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER device_tokens_updated_at BEFORE UPDATE ON device_tokens FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER user_settings_updated_at BEFORE UPDATE ON user_settings FOR EACH ROW EXECUTE FUNCTION update_updated_at();
