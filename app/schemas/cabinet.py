from datetime import datetime
from typing import Literal
from uuid import UUID

from app.schemas.base import PharmaBaseModel


class CabinetDTO(PharmaBaseModel):
    id: UUID
    owner_user_id: UUID
    name: str
    is_shared: bool
    created_at: datetime
    updated_at: datetime


class CabinetCreateRequest(PharmaBaseModel):
    name: str
    is_shared: bool = False


class CabinetUpdateRequest(PharmaBaseModel):
    name: str | None = None
    is_shared: bool | None = None


class CabinetMembershipDTO(PharmaBaseModel):
    id: UUID
    cabinet_id: UUID
    user_id: UUID
    role: Literal["owner", "editor", "viewer"]
    status: Literal["active", "invited", "revoked"]
    created_at: datetime
    updated_at: datetime


class CabinetMembershipCreateRequest(PharmaBaseModel):
    user_id: UUID
    role: Literal["editor", "viewer"]


class CabinetMembershipUpdateRequest(PharmaBaseModel):
    role: Literal["editor", "viewer"] | None = None
    status: Literal["active", "invited", "revoked"] | None = None


class CabinetWithMembershipsDTO(PharmaBaseModel):
    id: UUID
    owner_user_id: UUID
    name: str
    is_shared: bool
    created_at: datetime
    updated_at: datetime
    memberships: list[CabinetMembershipDTO] = []
