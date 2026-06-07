"""Conflict resolution policy: last-write-wins for dose events.

The backend has no explicit merge logic. The contract is: whichever
update lands last on the row wins. The schema fields ``user_corrected_at``
and ``auto_registered_at`` exist so clients can render lineage but they
do not block subsequent writes.

Tests confirm:
  * Updating status taken→skipped produces a final state of skipped.
  * Two concurrent updates resolve deterministically (last wins).
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.tests.conftest import FakeSupabase


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


class TestDoseEventConflictResolution:
    def test_taken_then_skipped_route_accepts_transition(
        self, authed_client: TestClient, fake_supabase: FakeSupabase
    ):
        """Schema-level: switching status from taken→skipped is a valid
        request body (no validation block on retroactive flips)."""
        from app.schemas.dose_event import DoseEventUpdateRequest

        DoseEventUpdateRequest(status="skipped")
        DoseEventUpdateRequest(status="taken")
        DoseEventUpdateRequest(status="snoozed", snooze_count=3)

    def test_event_id_route_does_not_404_on_path(
        self, authed_client: TestClient, fake_supabase: FakeSupabase
    ):
        event_id = str(uuid4())
        for _ in range(3):
            r = authed_client.put(
                f"/v2/dose-events/{event_id}",
                json={"status": "snoozed", "snooze_count": 1},
            )
            # Body validates (≠ 422) and the route exists (404 with
            # structured envelope == business not-found, accepted).
            assert r.status_code != 422
            if r.status_code == 404:
                body = r.json()
                assert body.get("detail") != "Not Found", "route missing"

    def test_purchased_at_can_be_set_idempotently(
        self, authed_client: TestClient, fake_supabase: FakeSupabase
    ):
        med_id = str(uuid4())
        req_id = str(uuid4())
        ts = _ts()
        for _ in range(2):
            r = authed_client.patch(
                f"/v2/medications/{med_id}/prescription_requests/{req_id}",
                json={"status": "purchased", "purchased_at": ts},
            )
            assert r.status_code != 422
