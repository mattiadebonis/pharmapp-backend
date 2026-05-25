"""Regression tests for the explicit profile-init flow that replaces the
implicit auto-create previously performed by GET /v2/bootstrap.

The auto-create masked Supabase anonymous-session rotation: a rotated
``sub`` claim would silently spawn an empty profile, and the iOS client's
guardrail (which only triggers when the remote bootstrap is *entirely*
empty) would let the local cache be overwritten. The fix is two-part:

1. ``GET /v2/bootstrap`` no longer creates profiles unless the legacy
   ``?auto_create_profile=true`` flag is set (kept for pre-init iOS
   builds during the rollout).
2. ``POST /v2/profiles/init`` is idempotent and the new home of profile
   provisioning. iOS calls it once at the end of onboarding.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.tests.conftest import TEST_USER_ID, FakeSupabase


def test_bootstrap_does_not_auto_create_profile_by_default(
    authed_client: TestClient, fake_supabase: FakeSupabase
) -> None:
    # No profiles seeded — the bootstrap MUST NOT insert one. Updated iOS
    # builds rely on the empty array to detect a rotated identity and
    # preserve the local cache instead of overwriting it.
    response = authed_client.get("/v2/bootstrap")
    assert response.status_code == 200
    payload = response.json()
    assert payload["profiles"] == [], "bootstrap auto-created a profile when it shouldn't"
    profile_inserts = fake_supabase.recorded_inserts.get("profiles", [])
    assert profile_inserts == [], "bootstrap performed a profile insert when auto_create_profile defaulted off"


def test_bootstrap_auto_create_legacy_flag_still_inserts(
    authed_client: TestClient, fake_supabase: FakeSupabase
) -> None:
    # Pre-init iOS builds keep working: when they request the legacy flag
    # explicitly, the backend still creates a default profile. This shim
    # is scheduled for removal once those builds are sunset.
    response = authed_client.get("/v2/bootstrap?auto_create_profile=true")
    assert response.status_code == 200
    profile_inserts = fake_supabase.recorded_inserts.get("profiles", [])
    assert len(profile_inserts) == 1
    inserted = profile_inserts[0]
    assert inserted["user_id"] == str(TEST_USER_ID)
    assert inserted["profile_type"] == "own"


def test_init_own_profile_creates_when_missing(
    authed_client: TestClient, fake_supabase: FakeSupabase
) -> None:
    response = authed_client.post("/v2/profiles/init")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["profile_type"] == "own"
    profile_inserts = fake_supabase.recorded_inserts.get("profiles", [])
    assert len(profile_inserts) == 1


def test_init_own_profile_is_idempotent(
    authed_client: TestClient, fake_supabase: FakeSupabase
) -> None:
    # Seed an existing 'own' profile — init must return it without
    # inserting a duplicate.
    fake_supabase.seed_select(
        "profiles",
        [
            {
                "id": "11111111-1111-4111-8111-111111111111",
                "user_id": str(TEST_USER_ID),
                "profile_type": "own",
                "display_name": "Io",
                "color": "#2B7DD4",
                "created_at": "2026-05-01T08:00:00+00:00",
                "updated_at": "2026-05-01T08:00:00+00:00",
            }
        ],
    )
    response = authed_client.post("/v2/profiles/init")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == "11111111-1111-4111-8111-111111111111"
    profile_inserts = fake_supabase.recorded_inserts.get("profiles", [])
    assert profile_inserts == [], "second init call inserted a duplicate profile"


def test_debug_whoami_returns_sub_and_counts(
    authed_client: TestClient, fake_supabase: FakeSupabase
) -> None:
    fake_supabase.seed_select(
        "profiles",
        [
            {
                "id": "11111111-1111-4111-8111-111111111111",
                "user_id": str(TEST_USER_ID),
                "profile_type": "own",
                "created_at": "2026-05-01T08:00:00+00:00",
            }
        ],
    )
    response = authed_client.get("/v2/debug/whoami")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["sub"] == str(TEST_USER_ID)
    assert body["profile_count"] == 1
    assert body["profile_ids"] == ["11111111-1111-4111-8111-111111111111"]
    # Anonymous detection is best-effort (peeks at JWT claims without
    # verifying signature). The TestClient has no auth header, so the
    # flag falls back to False.
    assert body["is_anonymous"] is False
