from datetime import datetime
from typing import Any
from uuid import UUID

from app.schemas.base import PharmaBaseModel


# ---------------------------------------------------------------------------
# DTO – full representation returned by the API
# ---------------------------------------------------------------------------
class ActivityLogDTO(PharmaBaseModel):
    id: UUID
    user_id: UUID
    profile_id: UUID | None = None
    medication_id: UUID | None = None
    action_type: str
    details: dict[str, Any] | None = None
    actor_user_id: UUID | None = None
    actor_device_id: str | None = None
    source: str | None = None
    created_at: datetime


# ---------------------------------------------------------------------------
# Create request
# ---------------------------------------------------------------------------
class ActivityLogCreateRequest(PharmaBaseModel):
    profile_id: UUID | None = None
    medication_id: UUID | None = None
    action_type: str
    details: dict[str, Any] | None = None
    actor_device_id: str | None = None
    source: str | None = None
