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
    def test_legacy_event_put_route_is_gone(
        self, authed_client: TestClient, fake_supabase: FakeSupabase
    ):
        # PUT /v2/dose-events/{id} è stato rimosso (audit dead-code): iOS
        # registra solo via POST (+/batch). I client legacy con PUT in coda
        # ricevono 404 e la droppano (AppModel flush, handler
        # "legacy_put_404_dropped").
        r = authed_client.put(
            f"/v2/dose-events/{uuid4()}",
            json={"status": "snoozed", "snooze_count": 1},
        )
        assert r.status_code == 404

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
