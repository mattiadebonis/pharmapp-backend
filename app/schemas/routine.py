from datetime import datetime
from typing import Literal
from uuid import UUID

from app.schemas.base import PharmaBaseModel


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
RoutineStepType = Literal["medication", "wait", "event"]


# ---------------------------------------------------------------------------
# Step DTO + create
# ---------------------------------------------------------------------------
class RoutineStepDTO(PharmaBaseModel):
    id: UUID
    routine_id: UUID
    position: int
    step_type: RoutineStepType
    # medication step
    medication_id: UUID | None = None
    dose_amount: str | None = None
    # wait step
    duration_minutes: int | None = None
    instructions: str | None = None
    # event step
    event_name: str | None = None
    created_at: datetime
    updated_at: datetime


class RoutineStepCreateRequest(PharmaBaseModel):
    """Inline step payload used inside a routine create/update request.

    The id is allocated server-side. position is required and 0-indexed.
    Caller must supply the fields that match step_type:
      * medication → medication_id (required), dose_amount (optional)
      * wait       → duration_minutes (required), instructions (optional)
      * event      → event_name (required)
    """

    position: int
    step_type: RoutineStepType
    medication_id: UUID | None = None
    dose_amount: str | None = None
    duration_minutes: int | None = None
    instructions: str | None = None
    event_name: str | None = None


# ---------------------------------------------------------------------------
# Routine DTO + create + update
# ---------------------------------------------------------------------------
class RoutineDTO(PharmaBaseModel):
    id: UUID
    profile_id: UUID
    name: str
    rrule: str | None = None
    start_time: str | None = None
    is_active: bool = True
    steps: list[RoutineStepDTO] = []
    created_at: datetime
    updated_at: datetime


class RoutineCreateRequest(PharmaBaseModel):
    profile_id: UUID
    name: str
    rrule: str | None = None
    start_time: str | None = None
    is_active: bool = True
    steps: list[RoutineStepCreateRequest] = []


class RoutineUpdateRequest(PharmaBaseModel):
    name: str | None = None
    rrule: str | None = None
    start_time: str | None = None
    is_active: bool | None = None
    # When provided, replaces the full step list (caller sends the desired
    # final ordering; server diffs internally). Omit to leave steps untouched.
    steps: list[RoutineStepCreateRequest] | None = None
