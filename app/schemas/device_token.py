from datetime import datetime
from typing import Literal
from uuid import UUID

from app.schemas.base import PharmaBaseModel


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
Platform = Literal["ios", "android"]


# ---------------------------------------------------------------------------
# DTO – full representation returned by the API
# ---------------------------------------------------------------------------
class DeviceTokenDTO(PharmaBaseModel):
    id: UUID
    user_id: UUID
    token: str
    platform: Platform
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Create request
# ---------------------------------------------------------------------------
class DeviceTokenCreateRequest(PharmaBaseModel):
    token: str
    platform: Platform
