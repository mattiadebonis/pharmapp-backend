from datetime import date, datetime
from typing import Literal
from uuid import UUID

from app.schemas.base import PharmaBaseModel


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
ProfileType = Literal["own", "assisted", "dependent"]


# ---------------------------------------------------------------------------
# DTO – full representation returned by the API
# ---------------------------------------------------------------------------
class ProfileDTO(PharmaBaseModel):
    id: UUID
    user_id: UUID
    profile_type: ProfileType
    display_name: str
    birth_date: date | None = None
    color: str | None = None
    emoji: str | None = None
    parent_user_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Create request – client-supplied fields only
# ---------------------------------------------------------------------------
class ProfileCreateRequest(PharmaBaseModel):
    profile_type: ProfileType
    display_name: str
    birth_date: date | None = None
    color: str | None = None
    emoji: str | None = None
    parent_user_id: UUID | None = None


# ---------------------------------------------------------------------------
# Update request – every field optional
# ---------------------------------------------------------------------------
class ProfileUpdateRequest(PharmaBaseModel):
    profile_type: ProfileType | None = None
    display_name: str | None = None
    birth_date: date | None = None
    color: str | None = None
    emoji: str | None = None
    parent_user_id: UUID | None = None
