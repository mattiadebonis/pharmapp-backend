from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from app.schemas.base import PharmaBaseModel


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
CaregiverRelationStatus = Literal["pending", "patient_confirmation", "active", "rejected", "revoked"]
PendingChangeStatus = Literal["pending", "approved", "rejected"]


# ---------------------------------------------------------------------------
# CaregiverRelation – DTO
# ---------------------------------------------------------------------------
class CaregiverRelationDTO(PharmaBaseModel):
    id: UUID
    patient_user_id: UUID
    caregiver_user_id: UUID | None = None
    invite_code: str | None = None
    invite_expires_at: datetime | None = None
    status: CaregiverRelationStatus
    permissions: list[str] | dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# CaregiverRelation – requests
# ---------------------------------------------------------------------------
class CaregiverInviteRequest(PharmaBaseModel):
    """Patient creates an invite for a caregiver."""
    permissions: list[str] | dict[str, Any] | None = None


class CaregiverAcceptRequest(PharmaBaseModel):
    """Caregiver accepts an invite using the code."""
    invite_code: str


# ---------------------------------------------------------------------------
# PendingChange – DTO
# ---------------------------------------------------------------------------
class PendingChangeDTO(PharmaBaseModel):
    id: UUID
    caregiver_relation_id: UUID
    medication_id: UUID | None = None
    change_type: str
    payload: dict[str, Any] | None = None
    status: PendingChangeStatus
    expires_at: datetime | None = None
    created_at: datetime


# ---------------------------------------------------------------------------
# PendingChange – create request
# ---------------------------------------------------------------------------
class PendingChangeCreateRequest(PharmaBaseModel):
    caregiver_relation_id: UUID
    medication_id: UUID | None = None
    change_type: str
    payload: dict[str, Any] | None = None
    expires_at: datetime | None = None
