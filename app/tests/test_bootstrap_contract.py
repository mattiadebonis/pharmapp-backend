"""Contract test for the /v2/bootstrap response shape.

Generates a canonical bootstrap JSON snapshot from a fully seeded fake
Supabase, and writes it to ``app/tests/fixtures/bootstrap_snapshot.json``.
The same file is copied into the iOS test bundle (see
``pharmapp-ios/PharmaAppTests/Fixtures/bootstrap_snapshot.json``); the
iOS contract test then decodes the snapshot into ``AppBootstrap`` and
fails the build if any field is missing or mistyped.

Update workflow when intentionally changing the bootstrap schema:

  1. Run ``UPDATE_SNAPSHOTS=1 pytest app/tests/test_bootstrap_contract.py``
  2. Copy ``app/tests/fixtures/bootstrap_snapshot.json`` to
     ``pharmapp-ios/PharmaAppTests/Fixtures/bootstrap_snapshot.json``
  3. Run the iOS contract test to confirm the decoder still accepts it.
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from app.tests.conftest import TEST_USER_ID, FakeSupabase

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SNAPSHOT_PATH = FIXTURES_DIR / "bootstrap_snapshot.json"


def _seed_full(supabase: FakeSupabase) -> None:
    """Pre-load the fake Supabase with one row per significant entity so
    every bootstrap branch is exercised in the snapshot."""
    profile_id = "11111111-1111-1111-1111-111111111111"
    medication_id = "22222222-2222-2222-2222-222222222222"
    schedule_id = "33333333-3333-3333-3333-333333333333"
    doctor_id = "44444444-4444-4444-4444-444444444444"
    routine_id = "55555555-5555-5555-5555-555555555555"
    parameter_id = "66666666-6666-6666-6666-666666666666"

    ts = "2026-05-01T08:00:00+00:00"

    supabase.seed_select(
        "profiles",
        [
            {
                "id": profile_id,
                "user_id": str(TEST_USER_ID),
                "profile_type": "own",
                "display_name": "Mattia",
                "color": "#2B7DD4",
                "emoji": "👤",
                "created_at": ts,
                "updated_at": ts,
            }
        ],
    )
    supabase.seed_select(
        "user_settings",
        [
            {
                "user_id": str(TEST_USER_ID),
                "catalog_country": "it",
                "default_tracking_mode": "passive",
                "grace_minutes": 120,
                "biometrics_enabled": False,
                "face_id_sensitive_actions": False,
                "anonymous_notifications": False,
                "hide_medication_names": False,
                "created_at": ts,
                "updated_at": ts,
            }
        ],
    )
    supabase.seed_select(
        "doctors",
        [
            {
                "id": doctor_id,
                "user_id": str(TEST_USER_ID),
                "name": "Mario",
                "surname": "Rossi",
                "specialization": "cardiologo",
                "profile_ids": [profile_id],
                "created_at": ts,
                "updated_at": ts,
            }
        ],
    )
    supabase.seed_select(
        "medications",
        [
            {
                "id": medication_id,
                "profile_id": profile_id,
                "name": "Tachipirina",
                "principle": "paracetamolo",
                "tracking_mode": "active",
                "requires_prescription": False,
                "is_paused": False,
                "is_archived": False,
                "shared_with_caregiver": False,
                "injection_sites": [],
                "created_at": ts,
                "updated_at": ts,
            }
        ],
    )
    supabase.seed_select(
        "dosing_schedules",
        [
            {
                "id": schedule_id,
                "medication_id": medication_id,
                "schedule_type": "scheduled",
                "times": [{"time": "08:00"}],
                "pills_per_dose": 1,
                "is_active": True,
                "importance": "standard",
                "notification_level": "normal",
                "notifications_silenced": False,
                "notify_day_before": False,
                "rrule": "FREQ=DAILY",
                "created_at": ts,
                "updated_at": ts,
            }
        ],
    )
    supabase.seed_select(
        "supplies",
        [
            {
                "id": "77777777-7777-7777-7777-777777777777",
                "medication_id": medication_id,
                "current_pills": 30,
                "pills_at_purchase": 30,
                "package_units": 30,
                "refill_threshold_days": 7,
                "created_at": ts,
                "updated_at": ts,
            }
        ],
    )
    supabase.seed_select("prescriptions", [])
    supabase.seed_select("prescription_requests", [])
    supabase.seed_select(
        "dose_events",
        [
            {
                "id": "88888888-8888-8888-8888-888888888888",
                "medication_id": medication_id,
                "dosing_schedule_id": schedule_id,
                "profile_id": profile_id,
                "due_at": ts,
                "status": "pending",
                "snooze_count": 0,
                "injection_site": None,
                "created_at": ts,
                "updated_at": ts,
            }
        ],
    )
    supabase.seed_select("activity_logs", [])
    supabase.seed_select("caregiver_relations", [])
    supabase.seed_select("device_tokens", [])
    supabase.seed_select(
        "routines",
        [
            {
                "id": routine_id,
                "profile_id": profile_id,
                "name": "Mattina osteoporosi",
                "rrule": "FREQ=WEEKLY;BYDAY=MO",
                "start_time": "07:00",
                "is_active": True,
                "created_at": ts,
                "updated_at": ts,
            }
        ],
    )
    supabase.seed_select("routine_steps", [])
    supabase.seed_select(
        "parameters",
        [
            {
                "id": parameter_id,
                "profile_id": profile_id,
                "parameter_key": f"custom:{parameter_id}",
                "name": "Glicemia",
                "unit": "mg/dL",
                "value_type": "numericSingle",
                "is_predefined": False,
                "created_at": ts,
            }
        ],
    )
    supabase.seed_select("measurements", [])
    supabase.seed_select(
        "subscriptions",
        [
            {
                "user_id": str(TEST_USER_ID),
                "tier": "pro",
                "is_trial_active": False,
                "expires_at": "2027-05-01T08:00:00+00:00",
                "last_validated_at": ts,
                "original_transaction_id": "txn-snapshot",
                "product_id": "com.pharmapp.pro.yearly",
                "environment": "production",
                "created_at": ts,
                "updated_at": ts,
            }
        ],
    )


# Fixed namespace so anchor slot ids are deterministic across runs. The
# value is arbitrary but stable; do not change it or snapshots churn.
_SLOT_ID_NAMESPACE = uuid.UUID("6f9619ff-8b86-d011-b42d-00c04fc964ff")


def _normalize(payload: dict) -> dict:
    """Replace volatile fields (timestamps that the service injects on
    read, uuid4-generated anchor slot ids) with stable placeholders so
    the snapshot diff is meaningful.

    Anchor slot ids are redacted to *deterministic UUIDs* (uuid5 over the
    anchor name + index) rather than free-form strings: the iOS
    ``AnchorSlot.id`` field decodes as a ``UUID``, so the snapshot must
    stay UUID-valid for ``BootstrapContractTests`` to decode it.
    """
    if "subscription" in payload and isinstance(payload["subscription"], dict):
        sub = payload["subscription"]
        if sub.get("last_validated_at"):
            sub["last_validated_at"] = "2026-05-01T08:00:00+00:00"
    for profile in payload.get("profiles", []) or []:
        for anchor in profile.get("anchors", []) or []:
            for idx, slot in enumerate(anchor.get("slots", []) or []):
                seed = f"slot-{anchor.get('name', 'unknown')}-{idx}"
                slot["id"] = str(uuid.uuid5(_SLOT_ID_NAMESPACE, seed))
    return payload


def test_bootstrap_snapshot_matches(authed_client: TestClient, fake_supabase: FakeSupabase):
    _seed_full(fake_supabase)
    resp = authed_client.get("/v2/bootstrap")
    assert resp.status_code == 200
    payload = _normalize(resp.json())

    actual = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)

    if os.environ.get("UPDATE_SNAPSHOTS"):
        FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
        SNAPSHOT_PATH.write_text(actual + "\n", encoding="utf-8")
        return

    assert SNAPSHOT_PATH.exists(), (
        f"Snapshot not found at {SNAPSHOT_PATH}. "
        "Re-run with UPDATE_SNAPSHOTS=1 to create it."
    )
    expected = SNAPSHOT_PATH.read_text(encoding="utf-8").rstrip("\n")
    assert actual == expected, (
        "Bootstrap response shape changed. If this is intentional, "
        "regenerate the snapshot via UPDATE_SNAPSHOTS=1 and copy the "
        "new file to the iOS test bundle."
    )


def test_bootstrap_snapshot_iOS_field_inventory(authed_client: TestClient, fake_supabase: FakeSupabase):
    """Independent assertion: the snapshot must contain every top-level
    key the iOS AppBootstrap struct decodes. Catches removals even when
    the snapshot file was forgotten."""
    _seed_full(fake_supabase)
    payload = authed_client.get("/v2/bootstrap").json()
    expected_keys = {
        "profiles",
        "medications",
        "doctors",
        "settings",
        "subscription",
        "dose_events",
        "caregiver_relations",
        "pending_changes",
        "prescription_requests",
        "routines",
        "parameters",
        "recent_measurements",
        "activity_logs",
        "device_tokens",
    }
    missing = expected_keys - set(payload.keys())
    assert not missing, f"Bootstrap response missing keys: {missing}"
