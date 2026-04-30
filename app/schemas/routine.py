"""Routine schema with inline polymorphic steps."""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.schemas.base import PharmaBaseModel
from app.schemas.routine_step import RoutineStepData, RoutineStepDTO


# ---------------------------------------------------------------------------
# Routine DTO
# ---------------------------------------------------------------------------


class RoutineDTO(PharmaBaseModel):
    id: UUID
    profile_id: UUID
    name: str
    rrule: str | None = None
    start_time: str | None = None  # "HH:MM"
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class RoutineWithStepsDTO(RoutineDTO):
    steps: list[RoutineStepDTO] = []


# ---------------------------------------------------------------------------
# Create + Update requests
# ---------------------------------------------------------------------------


_TIME_PATTERN = r"^\d{2}:\d{2}$"


class RoutineCreateRequest(PharmaBaseModel):
    profile_id: UUID
    name: str = Field(min_length=1, max_length=80)
    rrule: str | None = None
    start_time: str | None = Field(None, pattern=_TIME_PATTERN)
    is_active: bool = True
    steps: list[RoutineStepData] = []


class RoutineUpdateRequest(PharmaBaseModel):
    """Updates routine metadata only. To replace the step list use the
    granular `/routines/{id}/steps/*` endpoints (or the legacy `steps`
    field for backward compatibility with v1 clients)."""

    name: str | None = Field(None, min_length=1, max_length=80)
    rrule: str | None = None
    start_time: str | None = Field(None, pattern=_TIME_PATTERN)
    is_active: bool | None = None
    steps: list[RoutineStepData] | None = None
