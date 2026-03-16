from datetime import datetime
from uuid import UUID

from app.schemas.base import PharmaBaseModel


class MedicineEntryDTO(PharmaBaseModel):
    id: UUID
    tracked_medicine_id: UUID
    tracked_package_id: UUID
    cabinet_id: UUID | None = None
    deadline_month: int | None = None
    deadline_year: int | None = None
    purchase_operation_id: UUID | None = None
    reversed_by_operation_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class MedicineEntryCreateRequest(PharmaBaseModel):
    tracked_package_id: UUID
    cabinet_id: UUID | None = None
    deadline_month: int | None = None
    deadline_year: int | None = None
    purchase_operation_id: UUID | None = None


class MedicineEntryUpdateRequest(PharmaBaseModel):
    cabinet_id: UUID | None = None
    deadline_month: int | None = None
    deadline_year: int | None = None
