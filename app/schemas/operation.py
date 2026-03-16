from datetime import datetime
from uuid import UUID

from app.schemas.base import PharmaBaseModel


class OperationRequest(PharmaBaseModel):
    operation_id: UUID
    tracked_medicine_id: UUID
    tracked_package_id: UUID | None = None
    therapy_id: UUID | None = None
    scheduled_due_at: datetime | None = None
    actor_device_id: str | None = None
    source: str | None = None


class UndoOperationRequest(PharmaBaseModel):
    operation_id: UUID  # New operation_id for the undo itself
    reversal_of_operation_id: UUID  # The operation being undone
    tracked_medicine_id: UUID
    tracked_package_id: UUID | None = None
    therapy_id: UUID | None = None
    actor_device_id: str | None = None
    source: str | None = None


class OperationResultDTO(PharmaBaseModel):
    operation_id: UUID
    was_duplicate: bool
    activity_log_id: UUID | None = None
