"""Test per POST /v2/dose-events/batch — upsert idempotente del catch-up.

Il batch è usato dal client iOS per registrare in blocco le dosi passive
arretrate (id deterministici per slot). Contratto:
- 200 con ``{events, upserted}`` (upsert, non 201);
- ogni evento deve avere ``id`` (422 senza);
- max 200 eventi per richiesta (422 oltre);
- profilo non posseduto → 403 senza insert parziale;
- FK violation → 409 ``foreign_key_violation`` (come il POST singolo).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.tests.conftest import TEST_USER_ID

PROFILE_ID = str(uuid4())
OTHER_PROFILE_ID = str(uuid4())
MEDICATION_ID = str(uuid4())


def _seed_profiles(fake_supabase, profile_ids=None):
    fake_supabase.seed_select(
        "profiles",
        [{"id": pid, "user_id": str(TEST_USER_ID)} for pid in (profile_ids or [PROFILE_ID])],
    )


def _event(idx: int, *, profile_id: str = PROFILE_ID, event_id: str | None = "auto") -> dict:
    due = datetime(2026, 6, 1, 20, 0, tzinfo=timezone.utc) + timedelta(days=idx)
    body = {
        "id": str(uuid4()) if event_id == "auto" else event_id,
        "medication_id": MEDICATION_ID,
        "profile_id": profile_id,
        "due_at": due.isoformat(),
        "taken_at": due.isoformat(),
        "status": "taken",
        "snooze_count": 0,
        "auto_registered_at": due.isoformat(),
    }
    if body["id"] is None:
        body.pop("id")
    return body


def test_batch_upserts_events(authed_client, fake_supabase):
    _seed_profiles(fake_supabase)
    events = [_event(i) for i in range(3)]
    resp = authed_client.post("/v2/dose-events/batch", json={"events": events})
    assert resp.status_code == 200
    body = resp.json()
    assert body["upserted"] == 3
    assert len(body["events"]) == 3
    upserts = [q for q in fake_supabase.calls if q._table == "dose_events" and q._operation == "upsert"]
    assert len(upserts) == 1, "il batch deve fare un solo upsert, non N insert"
    assert upserts[0]._on_conflict == "id"
    # actor_user_id impostato server-side su ogni evento
    assert all(p["actor_user_id"] == str(TEST_USER_ID) for p in upserts[0]._payload)


def test_batch_is_idempotent_on_replay(authed_client, fake_supabase):
    _seed_profiles(fake_supabase)
    events = [_event(i) for i in range(2)]
    first = authed_client.post("/v2/dose-events/batch", json={"events": events})
    second = authed_client.post("/v2/dose-events/batch", json={"events": events})
    assert first.status_code == 200
    assert second.status_code == 200
    # Stessi id → l'upsert riconsegna le stesse righe, niente duplicati.
    ids_first = sorted(e["id"] for e in first.json()["events"])
    ids_second = sorted(e["id"] for e in second.json()["events"])
    assert ids_first == ids_second


def test_batch_rejects_foreign_profile(authed_client, fake_supabase):
    _seed_profiles(fake_supabase)  # l'utente possiede solo PROFILE_ID
    events = [_event(0), _event(1, profile_id=OTHER_PROFILE_ID)]
    resp = authed_client.post("/v2/dose-events/batch", json={"events": events})
    assert resp.status_code == 403
    # Nessun insert parziale: l'ownership check precede l'upsert.
    upserts = [q for q in fake_supabase.calls if q._table == "dose_events" and q._operation == "upsert"]
    assert not upserts


def test_batch_rejects_event_without_id(authed_client, fake_supabase):
    _seed_profiles(fake_supabase)
    events = [_event(0), _event(1, event_id=None)]
    resp = authed_client.post("/v2/dose-events/batch", json={"events": events})
    assert resp.status_code == 422


def test_batch_rejects_empty_and_oversize(authed_client, fake_supabase):
    _seed_profiles(fake_supabase)
    assert authed_client.post("/v2/dose-events/batch", json={"events": []}).status_code == 422
    oversize = [_event(i) for i in range(201)]
    assert authed_client.post("/v2/dose-events/batch", json={"events": oversize}).status_code == 422
