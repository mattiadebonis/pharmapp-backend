from datetime import datetime
from uuid import UUID

from app.schemas.base import PharmaBaseModel


class MonitoringMeasurementDTO(PharmaBaseModel):
    id: UUID
    tracked_medicine_id: UUID | None = None
    therapy_id: UUID | None = None
    todo_source_id: str | None = None
    kind: str
    dose_relation: str | None = None
    value_primary: float | None = None
    value_secondary: float | None = None
    unit: str | None = None
    measured_at: datetime
    scheduled_at: datetime | None = None
    created_at: datetime


class MonitoringMeasurementCreateRequest(PharmaBaseModel):
    tracked_medicine_id: UUID | None = None
    therapy_id: UUID | None = None
    todo_source_id: str | None = None
    kind: str
    dose_relation: str | None = None
    value_primary: float | None = None
    value_secondary: float | None = None
    unit: str | None = None
    measured_at: datetime
    scheduled_at: datetime | None = None
