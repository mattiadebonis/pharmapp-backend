from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from app.schemas.base import PharmaBaseModel


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
ScheduleType = Literal["scheduled", "as_needed", "cycle", "tapering"]
Importance = Literal["vital", "essential", "standard"]
NotificationLevel = Literal["normal", "alarm"]


# ---------------------------------------------------------------------------
# DTO – full representation returned by the API
# ---------------------------------------------------------------------------
class DosingScheduleDTO(PharmaBaseModel):
    id: UUID
    medication_id: UUID
    schedule_type: ScheduleType
    times: list[dict[str, Any]] | None = None  # [{time, label}]
    pills_per_dose: float | None = None
    max_per_day: int | None = None
    min_interval_hours: float | None = None
    condition: str | None = None
    cycle_days: int | None = None
    cycle_start_date: date | None = None
    tapering_steps: list[dict[str, Any]] | None = None
    rrule: str | None = None
    is_active: bool = True
    importance: Importance = "standard"
    notification_level: NotificationLevel = "normal"
    snooze_minutes: int | None = None
    notifications_silenced: bool = False
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Create request
# ---------------------------------------------------------------------------
class DosingScheduleCreateRequest(PharmaBaseModel):
    medication_id: UUID
    schedule_type: ScheduleType
    times: list[dict[str, Any]] | None = None
    pills_per_dose: float | None = None
    max_per_day: int | None = None
    min_interval_hours: float | None = None
    condition: str | None = None
    cycle_days: int | None = None
    cycle_start_date: date | None = None
    tapering_steps: list[dict[str, Any]] | None = None
    rrule: str | None = None
    is_active: bool = True
    importance: Importance = "standard"
    notification_level: NotificationLevel = "normal"
    snooze_minutes: int | None = None
    notifications_silenced: bool = False


# ---------------------------------------------------------------------------
# Update request
# ---------------------------------------------------------------------------
class DosingScheduleUpdateRequest(PharmaBaseModel):
    schedule_type: ScheduleType | None = None
    times: list[dict[str, Any]] | None = None
    pills_per_dose: float | None = None
    max_per_day: int | None = None
    min_interval_hours: float | None = None
    condition: str | None = None
    cycle_days: int | None = None
    cycle_start_date: date | None = None
    tapering_steps: list[dict[str, Any]] | None = None
    rrule: str | None = None
    is_active: bool | None = None
    importance: Importance | None = None
    notification_level: NotificationLevel | None = None
    snooze_minutes: int | None = None
    notifications_silenced: bool | None = None
