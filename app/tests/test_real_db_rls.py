"""RLS cross-user isolation tests.

Verify Postgres Row-Level Security policies actually deny user B from
reading user A's rows. The FastAPI backend uses the service_role key
(which bypasses RLS), so this test bypasses the backend and hits
PostgREST directly with an authenticated-role JWT.

Skipped unless ``TEST_SUPABASE_URL`` is set. Requires
``docker-compose.test.yml`` stack running.
"""

from __future__ import annotations

import os
import subprocess
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import httpx
import pytest
from jose import jwt

pytestmark = pytest.mark.integration

USER_A_ID = UUID("00000000-0000-4000-8000-00000000000A")
USER_B_ID = UUID("00000000-0000-4000-8000-00000000000B")
JWT_SECRET = "a-string-secret-at-least-32-characters-long"
DB_CONTAINER = os.environ.get("TEST_DB_CONTAINER", "pharmapp-backend-pharma-test-db-1")


def _exec_sql(sql: str) -> None:
    subprocess.run(
        ["docker", "exec", DB_CONTAINER, "psql", "-U", "postgres", "-d", "postgres", "-c", sql],
        check=True,
        capture_output=True,
        timeout=10,
    )


def _make_jwt(*, sub: UUID, role: str = "authenticated") -> str:
    return jwt.encode(
        {
            "sub": str(sub),
            "aud": "authenticated",
            "role": role,
            "iss": "supabase",
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
        },
        JWT_SECRET,
        algorithm="HS256",
    )


def _service_jwt() -> str:
    return jwt.encode(
        {
            "role": "service_role",
            "iss": "supabase",
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
        },
        JWT_SECRET,
        algorithm="HS256",
    )


@pytest.fixture(scope="module", autouse=True)
def setup_module():
    if not os.environ.get("TEST_SUPABASE_URL"):
        pytest.skip("TEST_SUPABASE_URL required")
    try:
        _exec_sql(
            f"INSERT INTO auth.users (id) VALUES "
            f"('{USER_A_ID}'), ('{USER_B_ID}') ON CONFLICT DO NOTHING;"
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        pytest.skip(f"Could not seed auth.users in {DB_CONTAINER}")
    yield
    # Cleanup — leave auth.users for other tests
    try:
        _exec_sql(
            f"DELETE FROM profiles WHERE user_id IN ('{USER_A_ID}', '{USER_B_ID}');"
        )
    except Exception:
        pass


@pytest.fixture
def base_url() -> str:
    return os.environ["TEST_SUPABASE_URL"].rstrip("/") + "/rest/v1"


def test_user_b_cannot_read_user_a_profile(base_url: str):
    """Seed a profile owned by user A via service_role, then attempt to
    read it as user B via authenticated JWT — RLS must hide the row."""
    profile_id = str(uuid4())
    service_token = _service_jwt()
    user_b_token = _make_jwt(sub=USER_B_ID)

    # Seed profile for user A bypassing RLS
    create_resp = httpx.post(
        f"{base_url}/profiles",
        headers={
            "Authorization": f"Bearer {service_token}",
            "apikey": service_token,
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        },
        json={
            "id": profile_id,
            "user_id": str(USER_A_ID),
            "profile_type": "own",
            "display_name": "Alice",
        },
    )
    assert create_resp.status_code in (200, 201), create_resp.text

    # Attempt to read it as user B → RLS should hide
    read_resp = httpx.get(
        f"{base_url}/profiles?id=eq.{profile_id}",
        headers={
            "Authorization": f"Bearer {user_b_token}",
            "apikey": user_b_token,
        },
    )
    assert read_resp.status_code == 200, read_resp.text
    rows = read_resp.json()
    assert rows == [], f"RLS leak: user B saw user A's profile: {rows}"

    # Sanity: service_role STILL sees it (RLS bypass)
    sanity = httpx.get(
        f"{base_url}/profiles?id=eq.{profile_id}",
        headers={
            "Authorization": f"Bearer {service_token}",
            "apikey": service_token,
        },
    )
    assert sanity.status_code == 200
    assert len(sanity.json()) == 1, "service_role should see all rows"


def test_user_a_can_read_own_profile(base_url: str):
    """Positive control: user A reads their own profile via authenticated
    JWT — RLS allows."""
    profile_id = str(uuid4())
    service_token = _service_jwt()
    user_a_token = _make_jwt(sub=USER_A_ID)

    create = httpx.post(
        f"{base_url}/profiles",
        headers={
            "Authorization": f"Bearer {service_token}",
            "apikey": service_token,
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        },
        json={
            "id": profile_id,
            "user_id": str(USER_A_ID),
            "profile_type": "own",
            "display_name": "Alice-2",
        },
    )
    assert create.status_code in (200, 201), create.text

    resp = httpx.get(
        f"{base_url}/profiles?id=eq.{profile_id}",
        headers={
            "Authorization": f"Bearer {user_a_token}",
            "apikey": user_a_token,
        },
    )
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    assert len(rows) == 1, f"User A should see own profile, got: {rows}"
    assert rows[0]["display_name"] == "Alice-2"


def test_anonymous_role_cannot_read_profiles(base_url: str):
    """Anonymous (no JWT or anon role) must be denied profiles access."""
    resp = httpx.get(f"{base_url}/profiles?limit=1")
    # 401 (no auth) or 200 with empty rows (anon role exists but has no SELECT)
    assert resp.status_code in (200, 401, 403), resp.text
    if resp.status_code == 200:
        assert resp.json() == [], "anon must not see profiles"
