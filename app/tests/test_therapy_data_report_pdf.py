"""PDF rendering test — verifies the endpoint returns a valid PDF
with the right content-type and the standard PDF magic header."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.auth.models import AuthenticatedUser
from app.dependencies import get_current_user, get_supabase
from app.main import app
from app.tests.fixtures.fake_supabase import FakeSupabase
from app.tests.fixtures.personas import (
    ANCHOR_DATE,
    MARCO_PROFILE_ID,
    MATTIA_PROFILE_ID,
    ROBERTO_PROFILE_ID,
    USER_ID,
    all_personas_seed,
)


def _require_weasyprint():
    """Skip if WeasyPrint can't load its native deps (Pango/Cairo).

    On macOS dev machines without `brew install pango`, the import
    raises OSError instead of ImportError. importorskip only catches
    ImportError, so we wrap manually."""
    try:
        import weasyprint  # noqa: F401
    except (ImportError, OSError) as exc:
        pytest.skip(f"weasyprint unavailable: {exc.__class__.__name__}")


@pytest.fixture
def fake_db():
    return FakeSupabase(seed=all_personas_seed())


@pytest.fixture(autouse=True)
def _reset_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client(fake_db, monkeypatch):
    pinned = datetime(
        ANCHOR_DATE.year, ANCHOR_DATE.month, ANCHOR_DATE.day, 23, 59, tzinfo=UTC
    )
    import app.services.adherence_service as svc

    real_dt = svc.datetime

    class _Pinned(real_dt):  # type: ignore[misc, valid-type]
        @classmethod
        def now(cls, tz=None):
            return pinned if tz is None else pinned.astimezone(tz)

    monkeypatch.setattr(svc, "datetime", _Pinned)

    app.dependency_overrides[get_supabase] = lambda: fake_db
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(user_id=USER_ID)
    return TestClient(app)


def test_pdf_endpoint_returns_pdf_for_marco(client):
    _require_weasyprint()
    r = client.get(
        f"/v2/profiles/{MARCO_PROFILE_ID}/therapy-data/report.pdf?period=28d"
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.content[:5] == b"%PDF-"
    assert len(r.content) > 4000


def test_pdf_endpoint_works_for_mattia(client):
    _require_weasyprint()
    r = client.get(f"/v2/profiles/{MATTIA_PROFILE_ID}/therapy-data/report.pdf")
    assert r.status_code == 200
    assert r.content[:5] == b"%PDF-"


def test_pdf_endpoint_works_for_roberto_long_view(client):
    _require_weasyprint()
    r = client.get(
        f"/v2/profiles/{ROBERTO_PROFILE_ID}/therapy-data/report.pdf?period=12mo"
    )
    assert r.status_code == 200
    assert r.content[:5] == b"%PDF-"
    assert len(r.content) > 5000


def test_html_renderer_smoke():
    """Verify the HTML rendering path independent of WeasyPrint."""
    pytest.importorskip("jinja2")
    from datetime import date
    from uuid import UUID

    from app.schemas.adherence import (
        AdherenceReport,
        AdherenceSummary,
        PeriodSpec,
    )
    from app.schemas.report import TherapyDataReport
    from app.services.pdf_report_service import render_html

    sample = TherapyDataReport(
        profile_id=UUID(int=0),
        period=PeriodSpec(kind="28d", from_=date(2026, 3, 24), to=date(2026, 4, 20)),
        bucket="per_dose",
        generated_at=datetime(2026, 4, 20, 14, 32, tzinfo=UTC),
        adherence=AdherenceReport(
            summary=AdherenceSummary(
                expected=0, taken=0, late=0, partial=0, skipped=0, rate_pct=0
            ),
            medications=[],
        ),
        parameters=[],
        notes=[],
    )
    html = render_html(sample, {"display_name": "Test User"})
    assert "Test User" in html
    assert "RIEPILOGO TERAPIE" in html
