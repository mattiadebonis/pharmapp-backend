from datetime import datetime
from typing import Literal
from uuid import UUID

from app.schemas.base import PharmaBaseModel


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
DoseEventStatus = Literal["pending", "taken", "missed", "skipped", "snoozed"]


# ---------------------------------------------------------------------------
# DTO – full representation returned by the API
# ---------------------------------------------------------------------------
class DoseEventDTO(PharmaBaseModel):
    id: UUID
    medication_id: UUID
    dosing_schedule_id: UUID | None = None
    profile_id: UUID
    due_at: datetime
    taken_at: datetime | None = None
    status: DoseEventStatus
    snooze_count: int = 0
    actor_user_id: UUID | None = None
    actor_device_id: str | None = None
    auto_registered_at: datetime | None = None
    user_corrected_at: datetime | None = None
    note: str | None = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Create request
# ---------------------------------------------------------------------------
class DoseEventCreateRequest(PharmaBaseModel):
    medication_id: UUID
    dosing_schedule_id: UUID | None = None
    profile_id: UUID
    due_at: datetime
    taken_at: datetime | None = None
    status: DoseEventStatus = "pending"
    snooze_count: int = 0
    actor_device_id: str | None = None
    auto_registered_at: datetime | None = None
    user_corrected_at: datetime | None = None
    note: str | None = None


# ---------------------------------------------------------------------------
# Update request
# ---------------------------------------------------------------------------
class DoseEventUpdateRequest(PharmaBaseModel):
    taken_at: datetime | None = None
    status: DoseEventStatus | None = None
    snooze_count: int | None = None
    actor_device_id: str | None = None
    auto_registered_at: datetime | None = None
    user_corrected_at: datetime | None = None
    note: str | None = None
