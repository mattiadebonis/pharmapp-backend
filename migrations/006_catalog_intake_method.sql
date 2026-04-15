-- Add intake_method column to catalog_it_packages
-- Derived from FORMA field: oral_solid, oral_capsule, oral_liquid, injectable, etc.
-- Used by the iOS app to determine stock tracking mode (discrete vs continuous)

ALTER TABLE catalog_it_packages
  ADD COLUMN IF NOT EXISTS intake_method text;

COMMENT ON COLUMN catalog_it_packages.intake_method IS
  'Intake method derived from FORMA: oral_solid, oral_capsule, oral_chew, oral_dissolve, oral_dissolve_water, oral_granules_powder, oral_liquid, injectable, injectable_prefilled, transdermal, rectal, vaginal, ophthalmic, auricular, inhalation, nasal, topical_skin, gas, implant, other, unknown';

CREATE INDEX IF NOT EXISTS idx_catalog_it_packages_intake_method
  ON catalog_it_packages (intake_method);
