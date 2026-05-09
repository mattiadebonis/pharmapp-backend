"""Therapy-data router: aggregated adherence + parameters + notes,
plus PDF export. Both endpoints share the same query parameters."""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from supabase import Client

from app.auth.models import AuthenticatedUser
from app.dependencies import get_current_user, get_supabase
from app.schemas.adherence import PeriodKind
from app.schemas.report import TherapyDataReport
from app.services.adherence_service import IncludeOpt, build_report

router = APIRouter(prefix="/profiles", tags=["Therapy Data"])

VALID_INCLUDES: set[IncludeOpt] = {"adherence", "parameters", "notes"}


def _parse_include(raw: str | None) -> set[IncludeOpt]:
    if not raw:
        return set(VALID_INCLUDES)
    parts = {p.strip() for p in raw.split(",") if p.strip()}
    invalid = parts - VALID_INCLUDES
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "bad_request",
                    "message": f"invalid include values: {sorted(invalid)}",
                }
            },
        )
    return parts  # type: ignore[return-value]


def _validate_custom(period: PeriodKind, range_from: date | None, range_to: date | None) -> None:
    if period == "custom" and (range_from is None or range_to is None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "bad_request",
                    "message": "period=custom requires both `from` and `to`",
                }
            },
        )
    if range_from and range_to and range_to < range_from:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "bad_request", "message": "`to` must be ≥ `from`"}},
        )


@router.get(
    "/{profile_id}/therapy-data",
    response_model=TherapyDataReport,
    response_model_by_alias=True,
)
async def get_therapy_data(
    profile_id: UUID,
    period: Annotated[PeriodKind, Query()] = "28d",
    range_from: Annotated[date | None, Query(alias="from")] = None,
    range_to: Annotated[date | None, Query(alias="to")] = None,
    medication_ids: Annotated[list[UUID] | None, Query()] = None,
    parameter_keys: Annotated[list[str] | None, Query()] = None,
    include: Annotated[str | None, Query()] = None,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
) -> TherapyDataReport:
    """Aggregated therapy data for a profile in a given period.

    Period kinds:
    - `7d`, `28d`: bucket=per_dose
    - `12mo`, `all`: bucket=per_month
    - `custom`: bucket auto-selected (per_dose ≤35 days, per_week ≤120, per_month otherwise)
    """
    _validate_custom(period, range_from, range_to)
    include_set = _parse_include(include)
    return await build_report(
        supabase, user.user_id, profile_id,
        period=period,
        range_from=range_from,
        range_to=range_to,
        medication_ids=medication_ids,
        parameter_keys=parameter_keys,
        include=include_set,
    )


@router.get("/{profile_id}/therapy-data/report.pdf")
async def export_therapy_data_pdf(
    profile_id: UUID,
    period: Annotated[PeriodKind, Query()] = "28d",
    range_from: Annotated[date | None, Query(alias="from")] = None,
    range_to: Annotated[date | None, Query(alias="to")] = None,
    medication_ids: Annotated[list[UUID] | None, Query()] = None,
    parameter_keys: Annotated[list[str] | None, Query()] = None,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
) -> Response:
    """Render the therapy-data report as a clinical PDF (A4)."""
    _validate_custom(period, range_from, range_to)
    report = await build_report(
        supabase, user.user_id, profile_id,
        period=period,
        range_from=range_from,
        range_to=range_to,
        medication_ids=medication_ids,
        parameter_keys=parameter_keys,
        include={"adherence", "parameters", "notes"},
    )
    profile_meta = await _fetch_profile_meta(supabase, profile_id)
    from app.services.pdf_report_service import render as render_pdf

    pdf_bytes = render_pdf(report, profile_meta)
    filename = f"report-clinico-{profile_id}-{report.generated_at.date().isoformat()}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


async def _fetch_profile_meta(supabase: Client, profile_id: UUID) -> dict:
    """Pull display name + birth_date for the PDF header."""
    rows = (
        supabase.table("profiles")
        .select("id, display_name, birth_date, profile_type")
        .eq("id", str(profile_id))
        .execute()
        .data
        or []
    )
    return rows[0] if rows else {"id": str(profile_id), "display_name": ""}
