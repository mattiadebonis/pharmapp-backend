"""HTML snapshot regression for therapy-data PDF report.

PDF byte diff is brittle (font subsetting + creation timestamps differ
each run). The HTML upstream of the WeasyPrint pass is deterministic
once we strip the timestamp footer, so we snapshot that instead.

Update workflow: ``UPDATE_SNAPSHOTS=1 pytest test_pdf_snapshot.py``,
inspect the diff, commit the new fixture.
"""

from __future__ import annotations

import os
import re
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import UUID

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "therapy_report_snapshot.html"


def _normalize(html: str) -> str:
    """Strip volatile values that drift each run (generated_at, run id)."""
    out = re.sub(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[\.\d+Z:-]*", "<TS>", html)
    # Strip whitespace differences between minor template tweaks.
    out = re.sub(r"\s+", " ", out).strip()
    return out


def test_therapy_report_html_snapshot():
    pytest.importorskip("jinja2")
    from app.schemas.adherence import AdherenceReport, AdherenceSummary, PeriodSpec
    from app.schemas.report import TherapyDataReport
    from app.services.pdf_report_service import render_html

    sample = TherapyDataReport(
        profile_id=UUID(int=0),
        period=PeriodSpec(kind="28d", from_=date(2026, 3, 24), to=date(2026, 4, 20)),
        bucket="per_dose",
        generated_at=datetime(2026, 4, 20, 14, 32, tzinfo=UTC),
        adherence=AdherenceReport(
            summary=AdherenceSummary(
                expected=10, taken=8, late=1, partial=0, skipped=1, rate_pct=80
            ),
            medications=[],
        ),
        parameters=[],
        notes=[],
    )
    html = render_html(sample, {"display_name": "Snapshot User"})
    actual = _normalize(html)

    if os.environ.get("UPDATE_SNAPSHOTS"):
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(actual + "\n", encoding="utf-8")
        return

    assert FIXTURE.exists(), (
        f"PDF HTML snapshot missing at {FIXTURE}. "
        "Run UPDATE_SNAPSHOTS=1 pytest to seed."
    )
    expected = FIXTURE.read_text(encoding="utf-8").rstrip("\n")
    assert actual == expected, (
        "PDF report HTML changed. If intentional, regenerate the snapshot "
        "via UPDATE_SNAPSHOTS=1 and review the diff."
    )


def test_therapy_report_pdf_magic_bytes():
    """PDF byte snapshot is too brittle, but the PDF magic header is
    a stable contract. Confirm WeasyPrint still emits a valid PDF."""
    try:
        import weasyprint  # noqa: F401
    except (OSError, ImportError):
        pytest.skip("WeasyPrint native deps not installed")

    from app.schemas.adherence import AdherenceReport, AdherenceSummary, PeriodSpec
    from app.schemas.report import TherapyDataReport
    from app.services.pdf_report_service import render

    sample = TherapyDataReport(
        profile_id=UUID(int=0),
        period=PeriodSpec(kind="28d", from_=date(2026, 3, 24), to=date(2026, 4, 20)),
        bucket="per_dose",
        generated_at=datetime(2026, 4, 20, 14, 32, tzinfo=UTC),
        adherence=AdherenceReport(
            summary=AdherenceSummary(expected=0, taken=0, late=0, partial=0, skipped=0, rate_pct=0),
            medications=[],
        ),
        parameters=[],
        notes=[],
    )
    pdf = render(sample, {"display_name": "Magic"})
    assert pdf[:5] == b"%PDF-"
    # Should be at least a few KB; empty PDFs indicate template breakage.
    assert len(pdf) > 1000
