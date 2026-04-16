from datetime import datetime
from typing import Literal
from uuid import UUID

from app.schemas.base import PharmaBaseModel


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
PrescriptionRequestChannel = Literal["whatsapp", "mail", "copy"]
PrescriptionRequestStatus = Literal["pending", "purchased", "cancelled"]


# ---------------------------------------------------------------------------
# DTO – full representation returned by the API
# ---------------------------------------------------------------------------
class PrescriptionRequestDTO(PharmaBaseModel):
    id: UUID
    medication_id: UUID
    doctor_id: UUID | None = None
    sent_at: datetime
    channel: PrescriptionRequestChannel
    status: PrescriptionRequestStatus = "pending"
    purchased_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Create request – the client generates the id so offline queues can keep it
# consistent across retries.
# ---------------------------------------------------------------------------
class PrescriptionRequestCreateRequest(PharmaBaseModel):
    id: UUID | None = None
    doctor_id: UUID | None = None
    sent_at: datetime | None = None
    channel: PrescriptionRequestChannel
    status: PrescriptionRequestStatus | None = None
    purchased_at: datetime | None = None


# ---------------------------------------------------------------------------
# Update request – used to mark a request as purchased or cancelled.
# ---------------------------------------------------------------------------
class PrescriptionRequestUpdateRequest(PharmaBaseModel):
    doctor_id: UUID | None = None
    channel: PrescriptionRequestChannel | None = None
    status: PrescriptionRequestStatus | None = None
    purchased_at: datetime | None = None
