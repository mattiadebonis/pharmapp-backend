from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.schemas.base import PharmaBaseModel


class MonitoringMeasurementDTO(PharmaBaseModel):
    id: UUID
    tracked_medicine_id: UUID | None = None
    therapy_id: UUID | None = None
    todo_source_id: str | None = None
    type: str = Field(validation_alias="kind")
    dose_relation: str | None = None
    value: float | None = Field(default=None, validation_alias="value_primary")
    value_secondary: float | None = None
    unit: str | None = None
    measured_at: datetime
    scheduled_at: datetime | None = None
    note: str | None = None
    created_at: datetime


class MonitoringMeasurementCreateRequest(PharmaBaseModel):
    tracked_medicine_id: UUID | None = None
    therapy_id: UUID | None = None
    todo_source_id: str | None = None
    kind: str = Field(validation_alias="type")
    dose_relation: str | None = None
    value_primary: float | None = Field(default=None, validation_alias="value")
    value_secondary: float | None = None
    unit: str | None = None
    measured_at: datetime
    scheduled_at: datetime | None = None
    note: str | None = None
