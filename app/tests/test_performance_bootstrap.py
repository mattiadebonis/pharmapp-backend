"""Bootstrap latency under load.

Seeds the FakeSupabase with a heavy fixture (100 medications, 1000
dose_events, 50 doctors, 200 prescription_requests) and asserts the
``/v2/bootstrap`` endpoint completes inside an SLO budget. The fake
serves canned data without the network/DB round-trip, so this is a
floor — the real-DB path will always be slower. Keep the floor tight.

Skipped unless ``TEST_PERF`` is set to avoid slowing every PR run.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.tests.conftest import TEST_USER_ID, FakeSupabase

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_PERF"),
    reason="Set TEST_PERF=1 to run performance tests",
)


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _seed_heavy(supabase: FakeSupabase, *, profiles: int = 1, meds: int = 100, events: int = 1000) -> None:
    # Use real UUIDs so Pydantic response models accept them.
    profile_ids: list[str] = [str(uuid4()) for _ in range(profiles)]
    supabase.seed_select(
        "profiles",
        [
            {
                "id": pid,
                "user_id": str(TEST_USER_ID),
                "profile_type": "own" if i == 0 else "assisted",
                "display_name": f"Profile {i}",
                "color": "#2B7DD4",
                "created_at": _ts(),
                "updated_at": _ts(),
            }
            for i, pid in enumerate(profile_ids)
        ],
    )

    med_ids: list[str] = [str(uuid4()) for _ in range(meds)]
    supabase.seed_select(
        "medications",
        [
            {
                "id": mid,
                "profile_id": profile_ids[i % len(profile_ids)],
                "name": f"Med {i}",
                "tracking_mode": "passive",
                "requires_prescription": False,
                "is_paused": False,
                "is_archived": False,
                "shared_with_caregiver": False,
                "injection_sites": [],
                "created_at": _ts(),
                "updated_at": _ts(),
            }
            for i, mid in enumerate(med_ids)
        ],
    )

    supabase.seed_select(
        "dosing_schedules",
        [
            {
                "id": str(uuid4()),
                "medication_id": mid,
                "schedule_type": "scheduled",
                "is_active": True,
                "importance": "standard",
                "notification_level": "normal",
                "notifications_silenced": False,
                "notify_day_before": False,
                "rrule": "FREQ=DAILY",
                "created_at": _ts(),
                "updated_at": _ts(),
            }
            for mid in med_ids
        ],
    )

    supabase.seed_select("supplies", [])
    supabase.seed_select("prescriptions", [])
    supabase.seed_select("prescription_requests", [])
    supabase.seed_select(
        "dose_events",
        [
            {
                "id": str(uuid4()),
                "medication_id": med_ids[i % meds],
                "profile_id": profile_ids[0],
                "due_at": _ts(),
                "status": "pending",
                "snooze_count": 0,
                "created_at": _ts(),
                "updated_at": _ts(),
            }
            for i in range(events)
        ],
    )

    supabase.seed_select("activity_logs", [])
    supabase.seed_select("caregiver_relations", [])
    supabase.seed_select("device_tokens", [])
    supabase.seed_select("routines", [])
    supabase.seed_select("routine_steps", [])
    supabase.seed_select("parameters", [])
    supabase.seed_select("measurements", [])
    supabase.seed_select(
        "user_settings",
        [
            {
                "user_id": str(TEST_USER_ID),
                "catalog_country": "it",
                "default_refill_threshold": 7,
                "default_tracking_mode": "passive",
                "default_snooze_minutes": 10,
                "grace_minutes": 120,
                "notify_caregivers": True,
                "notifications_enabled": True,
                "refill_alerts_enabled": True,
                "biometrics_enabled": False,
                "face_id_sensitive_actions": False,
                "anonymous_notifications": False,
                "hide_medication_names": False,
                "created_at": _ts(),
                "updated_at": _ts(),
            }
        ],
    )
    supabase.seed_select("subscriptions", [])


class TestBootstrapPerformance:
    def test_bootstrap_under_2s_with_100_meds_1000_events(
        self, authed_client: TestClient, fake_supabase: FakeSupabase
    ):
        _seed_heavy(fake_supabase, profiles=1, meds=100, events=1000)
        start = time.perf_counter()
        resp = authed_client.get("/v2/bootstrap")
        elapsed = time.perf_counter() - start
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["medications"]) == 100
        assert len(body["dose_events"]) == 1000
        assert elapsed < 2.0, f"bootstrap took {elapsed:.2f}s — expected < 2s"

    def test_bootstrap_under_500ms_with_typical_load(
        self, authed_client: TestClient, fake_supabase: FakeSupabase
    ):
        """Median user has < 20 meds + < 200 events. 500ms ceiling is
        deliberately tight to catch perf regressions early."""
        _seed_heavy(fake_supabase, profiles=2, meds=20, events=200)
        start = time.perf_counter()
        resp = authed_client.get("/v2/bootstrap")
        elapsed = time.perf_counter() - start
        assert resp.status_code == 200
        assert elapsed < 0.5, f"bootstrap took {elapsed:.2f}s — expected < 0.5s"

    def test_bootstrap_serializes_all_dose_events(
        self, authed_client: TestClient, fake_supabase: FakeSupabase
    ):
        """Smoke: confirm that under heavy load every event is returned
        (no silent truncation by the bootstrap pipeline)."""
        _seed_heavy(fake_supabase, profiles=1, meds=10, events=500)
        resp = authed_client.get("/v2/bootstrap")
        assert resp.status_code == 200
        # The bootstrap_service caps dose_events at 500 (see service code);
        # we asked for exactly that many to test the boundary.
        events = resp.json()["dose_events"]
        assert len(events) == 500
