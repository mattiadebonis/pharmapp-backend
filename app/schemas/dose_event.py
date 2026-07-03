from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.base import PharmaBaseModel

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
DoseEventStatus = Literal["pending", "taken", "missed", "skipped", "snoozed"]


# ---------------------------------------------------------------------------
# DTO – full representation returned by the API
# ---------------------------------------------------------------------------
class DoseEventDTO(PharmaBaseModel):
    id: UUID
    medication_id: UUID
    dosing_schedule_id: UUID | None = None
    profile_id: UUID
    due_at: datetime
    taken_at: datetime | None = None
    status: DoseEventStatus
    snooze_count: int = 0
    # Slot originale della posologia quando la dose è stata spostata
    # («Sposta orario»); NULL = mai spostata. Vedi migration 052.
    rescheduled_from: datetime | None = None
    actor_user_id: UUID | None = None
    actor_device_id: str | None = None
    auto_registered_at: datetime | None = None
    user_corrected_at: datetime | None = None
    note: str | None = None
    pills_taken: float | None = None
    injection_site: str | None = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Create request
# ---------------------------------------------------------------------------
class DoseEventCreateRequest(PharmaBaseModel):
    id: UUID | None = None
    medication_id: UUID
    dosing_schedule_id: UUID | None = None
    profile_id: UUID
    due_at: datetime
    taken_at: datetime | None = None
    status: DoseEventStatus = "pending"
    snooze_count: int = 0
    rescheduled_from: datetime | None = None
    actor_device_id: str | None = None
    auto_registered_at: datetime | None = None
    user_corrected_at: datetime | None = None
    note: str | None = None
    pills_taken: float | None = None
    injection_site: str | None = None


# ---------------------------------------------------------------------------
# Batch create request — usato dal catch-up iOS (dosi passive arretrate).
# Ogni evento DEVE avere `id`: il client genera id deterministici per slot,
# così il replay offline e il doppio device convergono sullo stesso upsert.
# ---------------------------------------------------------------------------
class DoseEventBatchCreateRequest(PharmaBaseModel):
    events: list[DoseEventCreateRequest] = Field(..., min_length=1, max_length=200)

    @field_validator("events")
    @classmethod
    def _all_events_have_id(cls, v: list[DoseEventCreateRequest]) -> list[DoseEventCreateRequest]:
        if any(event.id is None for event in v):
            raise ValueError("every event in a batch must carry a client-generated id")
        return v


class DoseEventBatchResponse(PharmaBaseModel):
    events: list[DoseEventDTO]
    upserted: int
