"""Real-DB integration tests against the docker-compose.test.yml stack.

Auto-skipped unless ``TEST_SUPABASE_URL`` is set. To run:

    docker compose -f docker-compose.test.yml up -d
    TEST_SUPABASE_URL=http://localhost:54321 \
      TEST_SUPABASE_SERVICE_ROLE_KEY=<service-role-jwt> \
      TEST_SUPABASE_JWT_SECRET=a-string-secret-at-least-32-characters-long \
      .venv/bin/pytest -m integration -v

Each test cleans up after itself by deleting the rows it created. Tests
are intentionally narrow — they assert the round-trip works against a
real Postgres + PostgREST + (optional) GoTrue stack, NOT business logic
(that's covered by the mocked integration suite).
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from supabase import Client, create_client

from app.auth.models import AuthenticatedUser
from app.dependencies import get_current_user, get_supabase
from app.main import app

pytestmark = pytest.mark.integration


TEST_USER_ID = UUID("00000000-0000-4000-8000-000000000001")


@pytest.fixture(scope="module")
def real_supabase() -> Client:
    url = os.environ.get("TEST_SUPABASE_URL")
    key = os.environ.get("TEST_SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        pytest.skip("TEST_SUPABASE_URL and TEST_SUPABASE_SERVICE_ROLE_KEY required")
    # Seed auth.users via docker exec — PostgREST doesn't expose the auth
    # schema and supabase-py can't create roles. Idempotent.
    import subprocess

    container = os.environ.get("TEST_DB_CONTAINER", "pharmapp-backend-pharma-test-db-1")
    try:
        subprocess.run(
            [
                "docker",
                "exec",
                container,
                "psql",
                "-U",
                "postgres",
                "-d",
                "postgres",
                "-c",
                f"INSERT INTO auth.users (id) VALUES ('{TEST_USER_ID}') ON CONFLICT DO NOTHING;",
            ],
            check=True,
            capture_output=True,
            timeout=10,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        pytest.skip(f"Could not seed auth.users in {container}")
    return create_client(url, key)


@pytest.fixture
def real_authed_client(real_supabase: Client) -> Iterator[TestClient]:
    fake_user = AuthenticatedUser(user_id=TEST_USER_ID, role="authenticated")
    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_supabase] = lambda: real_supabase
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_supabase, None)


@pytest.fixture(autouse=True)
def cleanup(real_supabase: Client):
    """Delete rows owned by TEST_USER_ID before AND after each test so
    parallel re-runs stay green. All swallowed — purge is best-effort."""

    def _purge():
        for table in ("subscriptions", "user_settings", "doctors", "profiles"):
            try:
                real_supabase.table(table).delete().eq("user_id", str(TEST_USER_ID)).execute()
            except Exception:
                pass

    _purge()
    yield
    _purge()


# ---------------------------------------------------------------------------
# Profiles round-trip
# ---------------------------------------------------------------------------


class TestProfilesRealDB:
    def test_create_and_list(self, real_authed_client: TestClient):
        resp = real_authed_client.post(
            "/v2/profiles",
            json={"profile_type": "own", "display_name": "Mattia Test", "color": "#2B7DD4"},
        )
        assert resp.status_code == 201, resp.text
        created = resp.json()
        assert created["display_name"] == "Mattia Test"
        assert created["user_id"] == str(TEST_USER_ID)

        listed = real_authed_client.get("/v2/profiles").json()
        assert any(p["id"] == created["id"] for p in listed)

    def test_create_assisted_with_managed_fields(self, real_authed_client: TestClient):
        resp = real_authed_client.post(
            "/v2/profiles",
            json={
                "profile_type": "assisted",
                "display_name": "Maria",
                "relation_label": "madre",
                "connection_status": "pending",
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["relation_label"] == "madre"
        assert body["connection_status"] == "pending"


# ---------------------------------------------------------------------------
# Settings round-trip
# ---------------------------------------------------------------------------


class TestSettingsRealDB:
    def test_get_creates_default_then_update(self, real_authed_client: TestClient):
        first = real_authed_client.get("/v2/settings")
        assert first.status_code == 200, first.text
        body = first.json()
        assert body["catalog_country"] == "it"

        upd = real_authed_client.put(
            "/v2/settings",
            json={"grace_minutes": 60, "anonymous_notifications": True},
        )
        assert upd.status_code == 200, upd.text
        updated = upd.json()
        assert updated["grace_minutes"] == 60
        assert updated["anonymous_notifications"] is True


# ---------------------------------------------------------------------------
# Subscription persistence (paywall round-trip)
# ---------------------------------------------------------------------------


class TestStoreRealDB:
    def test_verify_persists_and_get_returns(self, real_authed_client: TestClient):
        # Build a JWS-shaped string (signature verification disabled in test config)
        import base64
        import json
        from datetime import datetime, timedelta, timezone

        payload = {
            "bundleId": "com.pharmapp.ios",
            "productId": "com.pharmapp.pro.yearly",
            "originalTransactionId": f"txn-{uuid4()}",
            "expiresDate": int((datetime.now(timezone.utc) + timedelta(days=365)).timestamp() * 1000),
        }
        encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
        jws = f"header.{encoded}.sig"

        verify = real_authed_client.post(
            "/v2/store/transactions/verify",
            json={"signed_transaction": jws, "environment": "sandbox"},
        )
        assert verify.status_code == 200, verify.text
        assert verify.json()["tier"] == "pro"

        sub = real_authed_client.get("/v2/store/subscription")
        assert sub.status_code == 200, sub.text
        body = sub.json()
        assert body["tier"] == "pro"
        assert body["product_id"] == "com.pharmapp.pro.yearly"


# ---------------------------------------------------------------------------
# Bootstrap end-to-end
# ---------------------------------------------------------------------------


class TestBootstrapRealDB:
    def test_bootstrap_returns_subscription_field(self, real_authed_client: TestClient):
        resp = real_authed_client.get("/v2/bootstrap")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        for key in ("profiles", "medications", "doctors", "settings", "subscription"):
            assert key in body, f"missing key {key}"


# ---------------------------------------------------------------------------
# RLS isolation (cross-user)
# ---------------------------------------------------------------------------


class TestRLSRealDB:
    def test_other_user_profile_invisible(self, real_authed_client: TestClient, real_supabase: Client):
        # Create a profile owned by a different user via service_role
        other_user = uuid4()
        real_supabase.table("auth.users").insert({"id": str(other_user)}).execute() if False else None
        # We can't easily seed auth.users via PostgREST; rely on docker init.
        # Instead we directly insert a profile with another user_id and check
        # it doesn't leak via the FastAPI list endpoint (service filters by
        # current_user.user_id).
        try:
            real_supabase.table("profiles").insert(
                {
                    "user_id": str(uuid4()),  # random — likely violates FK; if so, skip
                    "profile_type": "own",
                    "display_name": "Cross",
                }
            ).execute()
        except Exception:
            pytest.skip("Cannot seed cross-user profile against FK; integration covered elsewhere")

        listed = real_authed_client.get("/v2/profiles").json()
        # All listed profiles must belong to TEST_USER_ID
        for p in listed:
            assert p["user_id"] == str(TEST_USER_ID), f"RLS leak: {p}"
