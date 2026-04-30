"""Measurement schema (recorded values).

Polymorphic by `parameter_key` value_type:
- numericSingle → `value_single`
- numericDouble → `value_double_1` + `value_double_2`
- text → `value_text`

Validation of value/type consistency happens in the service layer
(predefined parameter metadata lives in Python, not in the DB).
"""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.schemas.base import PharmaBaseModel


class MeasurementDTO(PharmaBaseModel):
    id: UUID
    profile_id: UUID
    parameter_key: str
    value_single: float | None = None
    value_double_1: float | None = None
    value_double_2: float | None = None
    value_text: str | None = None
    recorded_at: datetime
    routine_id: UUID | None = None
    routine_step_id: UUID | None = None
    note: str | None = None
    created_at: datetime


class MeasurementCreateRequest(PharmaBaseModel):
    profile_id: UUID
    parameter_key: str = Field(min_length=1, max_length=80)
    value_single: float | None = None
    value_double_1: float | None = None
    value_double_2: float | None = None
    value_text: str | None = Field(None, max_length=500)
    recorded_at: datetime | None = None
    routine_id: UUID | None = None
    routine_step_id: UUID | None = None
    note: str | None = Field(None, max_length=200)


class MeasurementUpdateRequest(PharmaBaseModel):
    value_single: float | None = None
    value_double_1: float | None = None
    value_double_2: float | None = None
    value_text: str | None = Field(None, max_length=500)
    recorded_at: datetime | None = None
    note: str | None = Field(None, max_length=200)
