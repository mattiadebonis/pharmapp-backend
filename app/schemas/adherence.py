"""Adherence DTOs.

Polymorphic per-medication payload that contains EITHER `bars`
(per-dose granularity), `monthly` (aggregated), or `sparkline`
(rolling rate). The bucket field on the parent `TherapyDataReport`
tells the consumer which list is populated.
"""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.schemas.base import PharmaBaseModel

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
PeriodKind = Literal["7d", "28d", "12mo", "all", "custom"]
BucketKind = Literal["per_dose", "per_week", "per_month"]
DoseDisplayStatus = Literal["regular", "late", "partial", "skipped", "not_due"]


# ---------------------------------------------------------------------------
# Period descriptor
# ---------------------------------------------------------------------------
class PeriodSpec(PharmaBaseModel):
    """Resolved time window for a report. `from` is a Python keyword,
    so the field is `from_` and serialised as `from`."""

    kind: PeriodKind
    from_: date = Field(serialization_alias="from", validation_alias="from")
    to: date


# ---------------------------------------------------------------------------
# Per-medication payload variants
# ---------------------------------------------------------------------------
class MedicationBar(PharmaBaseModel):
    """Single dose for the binary-bar visualisation (7d / 28d)."""

    due_at: datetime
    status: DoseDisplayStatus
    taken_at: datetime | None = None
    delay_min: int | None = None
    pills_expected: float | None = None
    pills_taken: float | None = None


class MedicationMonthlyAggregate(PharmaBaseModel):
    """One bucket (month or week) for the continuous-bar visualisation."""

    bucket: str  # "2026-04" for monthly, "2026-W14" for weekly
    expected: int
    taken: int
    late: int
    partial: int
    skipped: int
    rate_pct: float


class MedicationSparklinePoint(PharmaBaseModel):
    """One point of the rolling 7-day adherence trend (for `all` view)."""

    date: date
    rate_pct: float


class MedicationSeries(PharmaBaseModel):
    medication_id: UUID
    name: str
    color: str | None = None
    principle: str | None = None
    expected: int
    taken: int
    late: int
    partial: int
    skipped: int
    rate_pct: float
    bars: list[MedicationBar] | None = None
    monthly: list[MedicationMonthlyAggregate] | None = None
    sparkline: list[MedicationSparklinePoint] | None = None
    # Display-only schedule summary, e.g. ["06:30", "20:00"] or ["lun · mer · ven"].
    # Used by the PDF and mobile UI to surface dosing times in the
    # FARMACI list. Empty when the schedule is `as_needed`.
    schedule_label: str | None = None


# ---------------------------------------------------------------------------
# Aggregate report
# ---------------------------------------------------------------------------
class AdherenceSummary(PharmaBaseModel):
    expected: int
    taken: int
    late: int
    partial: int
    skipped: int
    rate_pct: float


class AdherenceReport(PharmaBaseModel):
    summary: AdherenceSummary
    medications: list[MedicationSeries]


# ---------------------------------------------------------------------------
# Parameters time series
# ---------------------------------------------------------------------------
class ParameterPoint(PharmaBaseModel):
    recorded_at: datetime
    v1: float | None = None
    v2: float | None = None


class ParameterSeries(PharmaBaseModel):
    parameter_key: str
    name: str
    unit: str | None = None
    value_type: Literal["numericSingle", "numericDouble", "text"]
    labels: list[str] | None = None
    points: list[ParameterPoint]


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------
class DoseNoteEntry(PharmaBaseModel):
    medication_id: UUID
    medication_name: str
    due_at: datetime
    snippet: str  # truncated to 140 chars
