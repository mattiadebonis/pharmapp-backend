from datetime import datetime
from uuid import UUID

from app.schemas.base import PharmaBaseModel


class ProfileDTO(PharmaBaseModel):
    id: UUID
    display_name: str | None = None
    photo_url: str | None = None
    created_at: datetime
    updated_at: datetime


class ProfileUpdateRequest(PharmaBaseModel):
    display_name: str | None = None
    photo_url: str | None = None
