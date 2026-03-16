from datetime import datetime
from typing import Literal
from uuid import UUID

from app.schemas.base import PharmaBaseModel


class DoseEventDTO(PharmaBaseModel):
    id: UUID
    therapy_id: UUID
    tracked_medicine_id: UUID
    due_at: datetime
    status: Literal["planned", "taken", "missed", "skipped"]
    actor_user_id: UUID | None = None
    actor_device_id: str | None = None
    created_at: datetime
    updated_at: datetime


class DoseEventCreateRequest(PharmaBaseModel):
    therapy_id: UUID
    tracked_medicine_id: UUID
    due_at: datetime
    status: Literal["planned", "taken", "missed", "skipped"]
    actor_device_id: str | None = None


class DoseEventUpdateRequest(PharmaBaseModel):
    status: Literal["planned", "taken", "missed", "skipped"]
    actor_device_id: str | None = None
