from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from app.schemas.base import PharmaBaseModel


CommunicationChannel = Literal["telefono", "whatsapp", "email"]


# ---------------------------------------------------------------------------
# DTO – full representation returned by the API
# ---------------------------------------------------------------------------
class DoctorDTO(PharmaBaseModel):
    id: UUID
    user_id: UUID
    name: str
    surname: str | None = None
    specialization: str | None = None
    study: str | None = None
    email: str | None = None
    phone: str | None = None
    whatsapp_phone: str | None = None
    address: str | None = None
    schedule_json: dict[str, Any] | None = None
    office_hours: str | None = None
    call_preferences: str | None = None
    secretary_name: str | None = None
    secretary_email: str | None = None
    secretary_phone: str | None = None
    secretary_schedule_json: dict[str, Any] | None = None
    secretary_office_hours: str | None = None
    prescription_message_template: str | None = None
    whatsapp_message_template: str | None = None
    preferenza_canale: CommunicationChannel | None = None
    profile_ids: list[UUID] = []
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Create request
# ---------------------------------------------------------------------------
class DoctorCreateRequest(PharmaBaseModel):
    id: UUID | None = None
    name: str
    surname: str | None = None
    specialization: str | None = None
    study: str | None = None
    email: str | None = None
    phone: str | None = None
    whatsapp_phone: str | None = None
    address: str | None = None
    schedule_json: dict[str, Any] | None = None
    office_hours: str | None = None
    call_preferences: str | None = None
    secretary_name: str | None = None
    secretary_email: str | None = None
    secretary_phone: str | None = None
    secretary_schedule_json: dict[str, Any] | None = None
    secretary_office_hours: str | None = None
    prescription_message_template: str | None = None
    whatsapp_message_template: str | None = None
    preferenza_canale: CommunicationChannel | None = None
    profile_ids: list[UUID] = []


# ---------------------------------------------------------------------------
# Update request
# ---------------------------------------------------------------------------
class DoctorUpdateRequest(PharmaBaseModel):
    name: str | None = None
    surname: str | None = None
    specialization: str | None = None
    study: str | None = None
    email: str | None = None
    phone: str | None = None
    whatsapp_phone: str | None = None
    address: str | None = None
    schedule_json: dict[str, Any] | None = None
    office_hours: str | None = None
    call_preferences: str | None = None
    secretary_name: str | None = None
    secretary_email: str | None = None
    secretary_phone: str | None = None
    secretary_schedule_json: dict[str, Any] | None = None
    secretary_office_hours: str | None = None
    prescription_message_template: str | None = None
    whatsapp_message_template: str | None = None
    preferenza_canale: CommunicationChannel | None = None
    profile_ids: list[UUID] = []
