"""Render the clinical PDF for each persona to /tmp/report-<name>.pdf.

Bypasses the FastAPI server: builds the report directly from the
FakeSupabase shim + persona fixtures, then renders via WeasyPrint.
Used for the pixel-perfect refinement loop without needing to seed
a real Supabase project.

Usage::

    DYLD_LIBRARY_PATH=/opt/homebrew/lib python -m scripts.render_personas_pdf
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import UUID

# Allow running as script (not module) by injecting the parent dir.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.services.adherence_service import build_report  # noqa: E402
from app.services.pdf_report_service import render as render_pdf  # noqa: E402
from app.tests.fixtures.fake_supabase import FakeSupabase  # noqa: E402
from app.tests.fixtures.personas import (  # noqa: E402
    ANCHOR_DATE,
    MARCO_PROFILE_ID,
    MATTIA_PROFILE_ID,
    ROBERTO_PROFILE_ID,
    USER_ID,
    all_personas_seed,
    marco_persona,
    mattia_persona,
    roberto_persona,
    roberto_pro_persona,
)


PINNED_NOW = datetime(
    ANCHOR_DATE.year, ANCHOR_DATE.month, ANCHOR_DATE.day, 23, 59, tzinfo=UTC
)


def _profile_meta(persona_seed) -> dict:
    return persona_seed["profiles"][0]


async def _render_one(
    label: str,
    profile_id: str,
    fake_db,
    period: str,
    range_from: date | None = None,
    range_to: date | None = None,
) -> bytes:
    report = await build_report(
        fake_db,
        USER_ID,
        UUID(profile_id),
        period=period,
        range_from=range_from,
        range_to=range_to,
        medication_ids=None,
        parameter_keys=None,
        include={"adherence", "parameters", "notes"},
        now=PINNED_NOW,
    )
    profile_meta = next(
        p for p in fake_db._tables["profiles"] if p["id"] == profile_id
    )
    pdf_bytes = render_pdf(report, profile_meta)
    return pdf_bytes


async def main() -> None:
    out_dir = Path("/tmp")
    fake_db_28 = FakeSupabase(seed=all_personas_seed())
    fake_db_pro = FakeSupabase(
        seed={
            **all_personas_seed(),
            # Replace Roberto's 28d events with the 6-month version
            **{
                k: v for k, v in roberto_pro_persona().items()
                if k in ("dose_events", "measurements")
            },
        }
    )

    six_months_ago = ANCHOR_DATE - timedelta(days=180)
    cases = [
        ("mattia", MATTIA_PROFILE_ID, fake_db_28, "28d", None, None),
        ("marco", MARCO_PROFILE_ID, fake_db_28, "28d", None, None),
        ("roberto", ROBERTO_PROFILE_ID, fake_db_28, "28d", None, None),
        ("roberto-pro", ROBERTO_PROFILE_ID, fake_db_pro, "custom",
         six_months_ago, ANCHOR_DATE),
    ]

    for label, profile_id, fake, period, rf, rt in cases:
        pdf_bytes = await _render_one(label, profile_id, fake, period, rf, rt)
        out_path = out_dir / f"report-{label}.pdf"
        out_path.write_bytes(pdf_bytes)
        print(f"  ✓ {out_path}  ({len(pdf_bytes):,} bytes)")


if __name__ == "__main__":
    asyncio.run(main())
