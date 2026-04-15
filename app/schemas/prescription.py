from datetime import date, datetime
from typing import Literal
from uuid import UUID

from app.schemas.base import PharmaBaseModel


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
PrescriptionType = Literal["ricetta_rossa", "ricetta_bianca", "specialist"]
PrescriptionRequestStatus = Literal["received", "requested", "expired"]


# ---------------------------------------------------------------------------
# DTO – full representation returned by the API
# ---------------------------------------------------------------------------
class PrescriptionDTO(PharmaBaseModel):
    id: UUID
    medication_id: UUID
    doctor_id: UUID | None = None
    prescription_type: PrescriptionType | None = None
    issued_date: date | None = None
    expiry_date: date | None = None
    total_packages: int | None = None
    remaining_packages: int | None = None
    notes: str | None = None
    requested_at: datetime | None = None
    request_status: PrescriptionRequestStatus = "received"
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Create request
# ---------------------------------------------------------------------------
class PrescriptionCreateRequest(PharmaBaseModel):
    medication_id: UUID
    doctor_id: UUID | None = None
    prescription_type: PrescriptionType | None = None
    issued_date: date | None = None
    expiry_date: date | None = None
    total_packages: int | None = None
    remaining_packages: int | None = None
    notes: str | None = None
    requested_at: datetime | None = None
    request_status: PrescriptionRequestStatus | None = None


# ---------------------------------------------------------------------------
# Update request
# ---------------------------------------------------------------------------
class PrescriptionUpdateRequest(PharmaBaseModel):
    doctor_id: UUID | None = None
    prescription_type: PrescriptionType | None = None
    issued_date: date | None = None
    expiry_date: date | None = None
    total_packages: int | None = None
    remaining_packages: int | None = None
    notes: str | None = None
    requested_at: datetime | None = None
    request_status: PrescriptionRequestStatus | None = None
