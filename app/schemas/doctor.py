from datetime import datetime
from typing import Any
from uuid import UUID

from app.schemas.base import PharmaBaseModel


# ---------------------------------------------------------------------------
# DTO – full representation returned by the API
# ---------------------------------------------------------------------------
class DoctorDTO(PharmaBaseModel):
    id: UUID
    user_id: UUID
    name: str
    surname: str | None = None
    specialization: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    schedule_json: dict[str, Any] | None = None
    secretary_name: str | None = None
    secretary_email: str | None = None
    secretary_phone: str | None = None
    secretary_schedule_json: dict[str, Any] | None = None
    prescription_message_template: str | None = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Create request
# ---------------------------------------------------------------------------
class DoctorCreateRequest(PharmaBaseModel):
    name: str
    surname: str | None = None
    specialization: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    schedule_json: dict[str, Any] | None = None
    secretary_name: str | None = None
    secretary_email: str | None = None
    secretary_phone: str | None = None
    secretary_schedule_json: dict[str, Any] | None = None
    prescription_message_template: str | None = None


# ---------------------------------------------------------------------------
# Update request
# ---------------------------------------------------------------------------
class DoctorUpdateRequest(PharmaBaseModel):
    name: str | None = None
    surname: str | None = None
    specialization: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    schedule_json: dict[str, Any] | None = None
    secretary_name: str | None = None
    secretary_email: str | None = None
    secretary_phone: str | None = None
    secretary_schedule_json: dict[str, Any] | None = None
    prescription_message_template: str | None = None
