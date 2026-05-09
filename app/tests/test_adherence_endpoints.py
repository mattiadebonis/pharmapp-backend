"""Integration tests for the /v2/profiles/{id}/therapy-data endpoint.

Uses an in-memory FakeSupabase so the suite runs without a real DB.
Auth is mocked by overriding `get_current_user`."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.auth.models import AuthenticatedUser
from app.dependencies import get_current_user, get_supabase
from app.main import app
from app.tests.fixtures.fake_supabase import FakeSupabase
from app.tests.fixtures.personas import (
    ANCHOR_DATE,
    ANOTHER_USER_ID,
    MARCO_PROFILE_ID,
    MATTIA_PROFILE_ID,
    USER_ID,
    all_personas_seed,
)


@pytest.fixture
def fake_db():
    return FakeSupabase(seed=all_personas_seed())


@pytest.fixture(autouse=True)
def _reset_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def pinned_now(monkeypatch):
    """Pin `datetime.now()` inside the adherence service so the
    skip-vs-not-due classification is deterministic across runs."""
    pinned = datetime(
        ANCHOR_DATE.year, ANCHOR_DATE.month, ANCHOR_DATE.day, 23, 59, tzinfo=UTC
    )
    import app.services.adherence_service as svc

    real_dt = svc.datetime

    class _Pinned(real_dt):  # type: ignore[misc, valid-type]
        @classmethod
        def now(cls, tz=None):  # noqa: D401
            return pinned if tz is None else pinned.astimezone(tz)

    monkeypatch.setattr(svc, "datetime", _Pinned)
    return pinned


@pytest.fixture
def client(fake_db, pinned_now):
    app.dependency_overrides[get_supabase] = lambda: fake_db
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(user_id=USER_ID)
    return TestClient(app)


def test_unauth_returns_401_or_403():
    """Without overriding auth, real JWT validation kicks in → 401/403."""
    c = TestClient(app)
    r = c.get(f"/v2/profiles/{MATTIA_PROFILE_ID}/therapy-data")
    assert r.status_code in (401, 403)


def test_foreign_user_gets_403(fake_db, pinned_now):
    app.dependency_overrides[get_supabase] = lambda: fake_db
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(user_id=ANOTHER_USER_ID)
    c = TestClient(app)
    r = c.get(f"/v2/profiles/{MATTIA_PROFILE_ID}/therapy-data")
    assert r.status_code == 403


def test_default_period_is_28d_per_dose(client):
    r = client.get(f"/v2/profiles/{MATTIA_PROFILE_ID}/therapy-data")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["bucket"] == "per_dose"
    assert data["period"]["kind"] == "28d"
    assert data["adherence"]["medications"]
    bars = data["adherence"]["medications"][0]["bars"]
    assert bars is not None and len(bars) == 28


def test_period_12mo_yields_per_month_buckets(client):
    r = client.get(f"/v2/profiles/{MATTIA_PROFILE_ID}/therapy-data?period=12mo")
    assert r.status_code == 200
    data = r.json()
    assert data["bucket"] == "per_month"
    med0 = data["adherence"]["medications"][0]
    assert med0["bars"] is None
    assert med0["monthly"] is not None


def test_include_filter_skips_parameters_and_notes(client):
    r = client.get(f"/v2/profiles/{MARCO_PROFILE_ID}/therapy-data?include=adherence")
    assert r.status_code == 200
    data = r.json()
    assert data["adherence"] is not None
    assert data["parameters"] is None
    assert data["notes"] is None


def test_invalid_include_returns_400(client):
    r = client.get(f"/v2/profiles/{MARCO_PROFILE_ID}/therapy-data?include=foo")
    assert r.status_code == 400


def test_custom_without_dates_returns_400(client):
    r = client.get(f"/v2/profiles/{MARCO_PROFILE_ID}/therapy-data?period=custom")
    assert r.status_code == 400


def test_marco_has_blood_pressure_series(client):
    r = client.get(f"/v2/profiles/{MARCO_PROFILE_ID}/therapy-data?period=28d")
    assert r.status_code == 200
    data = r.json()
    keys = [p["parameter_key"] for p in data["parameters"]]
    assert "blood_pressure" in keys
    bp = next(p for p in data["parameters"] if p["parameter_key"] == "blood_pressure")
    assert bp["value_type"] == "numericDouble"
    assert all(p["v1"] is not None and p["v2"] is not None for p in bp["points"])


def test_mattia_has_at_least_one_note(client):
    r = client.get(f"/v2/profiles/{MATTIA_PROFILE_ID}/therapy-data?period=28d")
    assert r.status_code == 200
    data = r.json()
    notes = data["notes"]
    assert notes is not None and len(notes) >= 1
    assert any("mal di stomaco" in (n["snippet"] or "").lower() for n in notes)


def test_per_dose_bars_count_matches_window(client):
    """Mattia has 1 dose/day for each of 2 meds → exactly 28 bars per med."""
    r = client.get(f"/v2/profiles/{MATTIA_PROFILE_ID}/therapy-data?period=28d")
    data = r.json()
    for m in data["adherence"]["medications"]:
        assert len(m["bars"]) == 28


def test_summary_aggregates_across_medications(client):
    r = client.get(f"/v2/profiles/{MATTIA_PROFILE_ID}/therapy-data?period=28d")
    data = r.json()
    summary = data["adherence"]["summary"]
    # 28 expected for each of 2 meds
    assert summary["expected"] == 56
    # 1 saltata Eutirox + 2 saltate VitD = 3 skipped
    assert summary["skipped"] == 3
