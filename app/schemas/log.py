from datetime import datetime
from uuid import UUID

from app.schemas.base import PharmaBaseModel


class ActivityLogDTO(PharmaBaseModel):
    id: UUID
    owner_user_id: UUID
    cabinet_id: UUID | None = None
    tracked_medicine_id: UUID | None = None
    tracked_package_id: UUID | None = None
    therapy_id: UUID | None = None
    operation_id: UUID | None = None
    reversal_of_operation_id: UUID | None = None
    type: str
    timestamp: datetime
    scheduled_due_at: datetime | None = None
    actor_user_id: UUID | None = None
    actor_device_id: str | None = None
    source: str | None = None
    created_at: datetime | None = None
