"""Test fixtures.

Two fixture flavors are exposed:

* ``client`` — bare TestClient (no auth, no DB) for routability and unit
  tests. Existing tests use this one.
* ``authed_client`` — TestClient with auth + DB dependencies overridden
  by an in-memory fake Supabase that records inserts/updates and serves
  back canned rows. Use this for service-level integration tests where
  the goal is to exercise the FastAPI route → service → DB-shaped query
  chain without spinning up Postgres.

For real DB-backed integration tests (``-m integration``), spin up the
local stack via ``docker compose -f docker-compose.test.yml up -d`` and
set ``TEST_SUPABASE_URL`` + ``TEST_SUPABASE_SERVICE_ROLE_KEY``. The
``real_supabase`` fixture below skips itself when those are missing.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.auth.models import AuthenticatedUser
from app.dependencies import get_current_user, get_supabase
from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# Mocked Supabase for integration-style tests
# ---------------------------------------------------------------------------


TEST_USER_ID = UUID("00000000-0000-4000-8000-000000000001")


class FakeQuery:
    """Minimal stand-in for the chainable supabase-py query builder.

    Records every method call and returns a SimpleNamespace-like result on
    ``.execute()``. Tests can pre-seed responses via the parent
    ``FakeSupabase`` and inspect inserts/updates afterwards."""

    def __init__(self, parent: "FakeSupabase", table: str):
        self._parent = parent
        self._table = table
        self._operation: str | None = None
        self._payload: Any = None
        self._filters: list[tuple[str, str, Any]] = []
        self._order: tuple[str, bool] | None = None
        self._limit_value: int | None = None
        self._on_conflict: str | None = None

    # CRUD
    def select(self, *_args, **_kwargs) -> "FakeQuery":
        self._operation = "select"
        return self

    def insert(self, payload, **_kwargs) -> "FakeQuery":
        self._operation = "insert"
        self._payload = payload
        return self

    def update(self, payload, **_kwargs) -> "FakeQuery":
        self._operation = "update"
        self._payload = payload
        return self

    def upsert(self, payload, on_conflict: str | None = None, **_kwargs) -> "FakeQuery":
        self._operation = "upsert"
        self._payload = payload
        self._on_conflict = on_conflict
        return self

    def delete(self, *_args, **_kwargs) -> "FakeQuery":
        self._operation = "delete"
        return self

    # Filters
    def eq(self, col, val) -> "FakeQuery":
        self._filters.append(("eq", col, val))
        return self

    def neq(self, col, val) -> "FakeQuery":
        self._filters.append(("neq", col, val))
        return self

    def in_(self, col, val) -> "FakeQuery":
        self._filters.append(("in", col, val))
        return self

    def order(self, col, desc: bool = False) -> "FakeQuery":
        self._order = (col, desc)
        return self

    def limit(self, n: int) -> "FakeQuery":
        self._limit_value = n
        return self

    def range(self, start: int, end: int) -> "FakeQuery":
        self._limit_value = end - start + 1
        return self

    def single(self) -> "FakeQuery":
        return self

    def maybe_single(self) -> "FakeQuery":
        return self

    def gte(self, col, val) -> "FakeQuery":
        self._filters.append(("gte", col, val))
        return self

    def lte(self, col, val) -> "FakeQuery":
        self._filters.append(("lte", col, val))
        return self

    def execute(self):
        self._parent.record_call(self)
        result = self._parent.canned_response(self._table, self._operation)
        return MagicMock(data=result)


class FakeSupabase:
    """Records query operations + serves canned data per table."""

    def __init__(self):
        self.calls: list[FakeQuery] = []
        self._canned: dict[tuple[str, str], list[dict[str, Any]]] = {}

    def table(self, name: str) -> FakeQuery:
        return FakeQuery(self, name)

    def rpc(self, *_a, **_kw):
        return MagicMock(execute=lambda: MagicMock(data=[]))

    def record_call(self, query: FakeQuery) -> None:
        self.calls.append(query)

    def canned_response(self, table: str, operation: str | None) -> list[dict[str, Any]]:
        # Insert/update/upsert echo the payload back wrapped in the right
        # shape, with synthetic id/created_at/updated_at columns so DTO
        # validators that require them succeed.
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()

        # Tables whose primary key is not a surrogate ``id`` column. We
        # avoid adding the synthetic id so DTO schemas without an ``id``
        # field (UserSettingsDTO, SubscriptionStateDTO) still validate.
        PK_NOT_ID = {"user_settings", "subscriptions"}

        def _enrich(p: dict[str, Any]) -> dict[str, Any]:
            base: dict[str, Any] = {
                "created_at": p.get("created_at") or now,
                "updated_at": p.get("updated_at") or now,
            }
            if table not in PK_NOT_ID:
                base["id"] = p.get("id") or str(uuid4())
            return {**base, **p}

        for query in reversed(self.calls):
            if query._table == table and query._operation in {"insert", "update", "upsert"}:
                payload = query._payload
                if isinstance(payload, list):
                    return [_enrich(item) if isinstance(item, dict) else item for item in payload]
                if isinstance(payload, dict):
                    return [_enrich(payload)]
        # Selects return whatever the test pre-seeded.
        return list(self._canned.get((table, "select"), []))

    def seed_select(self, table: str, rows: list[dict[str, Any]]) -> None:
        self._canned[(table, "select")] = rows

    @property
    def recorded_inserts(self) -> dict[str, list[Any]]:
        """Map of table → list of insert payloads (FIFO). Convenience for
        tests that want to assert downstream side-effects of a route call,
        e.g. that a `medications` POST also persisted embedded schedules
        into `dosing_schedules`."""
        result: dict[str, list[Any]] = {}
        for query in self.calls:
            if query._operation == "insert":
                result.setdefault(query._table, []).append(query._payload)
        return result


@pytest.fixture
def fake_supabase() -> FakeSupabase:
    return FakeSupabase()


@pytest.fixture
def fake_user() -> AuthenticatedUser:
    return AuthenticatedUser(user_id=TEST_USER_ID, role="authenticated")


@pytest.fixture
def authed_client(fake_supabase: FakeSupabase, fake_user: AuthenticatedUser) -> Iterator[TestClient]:
    """TestClient where auth + Supabase dependencies are overridden so any
    /v2 endpoint can be exercised. Use ``fake_supabase`` to pre-seed
    responses and assert calls afterwards."""
    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_supabase] = lambda: fake_supabase
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_supabase, None)


# ---------------------------------------------------------------------------
# Optional real-DB integration tests
# ---------------------------------------------------------------------------


def pytest_collection_modifyitems(config, items):
    """Auto-skip ``@pytest.mark.integration`` tests when the test stack
    is not running."""
    if os.getenv("TEST_SUPABASE_URL"):
        return
    skip_integration = pytest.mark.skip(
        reason="Set TEST_SUPABASE_URL to run DB-backed integration tests "
        "(see docker-compose.test.yml)."
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)
