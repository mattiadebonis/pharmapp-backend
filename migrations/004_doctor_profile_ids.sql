-- ============================================================
-- Add profile_ids to doctors (many-to-many doctor ↔ profile)
-- ============================================================

ALTER TABLE doctors ADD COLUMN IF NOT EXISTS profile_ids UUID[] NOT NULL DEFAULT '{}';

-- Backfill: assign existing doctors to the owner's primary profile
UPDATE doctors d
SET profile_ids = ARRAY(
    SELECT p.id FROM profiles p
    WHERE p.user_id = d.user_id AND p.profile_type = 'own'
    LIMIT 1
)
WHERE array_length(d.profile_ids, 1) IS NULL OR array_length(d.profile_ids, 1) = 0;
