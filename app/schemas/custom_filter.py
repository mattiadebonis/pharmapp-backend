from datetime import datetime
from uuid import UUID

from app.schemas.base import PharmaBaseModel


class CustomFilterDTO(PharmaBaseModel):
    id: UUID
    owner_user_id: UUID
    name: str
    query: str
    position: int
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


class CustomFilterCreateRequest(PharmaBaseModel):
    name: str
    query: str
    position: int = 0


class CustomFilterUpdateRequest(PharmaBaseModel):
    name: str | None = None
    query: str | None = None
    position: int | None = None
