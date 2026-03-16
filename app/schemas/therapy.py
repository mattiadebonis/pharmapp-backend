from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from app.schemas.base import PharmaBaseModel


class TherapyDoseDTO(PharmaBaseModel):
    id: UUID
    therapy_id: UUID
    time: str  # HH:MM:SS format
    amount: float
    sort_order: int


class TherapyDTO(PharmaBaseModel):
    id: UUID
    tracked_medicine_id: UUID
    tracked_package_id: UUID
    medicine_entry_id: UUID | None = None
    person_id: UUID
    doctor_id: UUID | None = None
    start_date: datetime
    rrule: str | None = None
    importance: Literal["vital", "essential", "standard"]
    notification_level: Literal["normal", "alarm"]
    notifications_silenced: bool
    snooze_minutes: int
    clinical_rules: dict[str, Any] = {}
    condition: str | None = None
    created_at: datetime
    updated_at: datetime


class TherapyWithDosesDTO(TherapyDTO):
    doses: list[TherapyDoseDTO] = []


class TherapyDoseInput(PharmaBaseModel):
    time: str  # HH:MM:SS format
    amount: float


class TherapyCreateRequest(PharmaBaseModel):
    tracked_package_id: UUID
    medicine_entry_id: UUID | None = None
    person_id: UUID
    doctor_id: UUID | None = None
    start_date: datetime
    rrule: str | None = None
    importance: Literal["vital", "essential", "standard"] = "standard"
    notification_level: Literal["normal", "alarm"] = "normal"
    notifications_silenced: bool = False
    snooze_minutes: int = 10
    clinical_rules: dict[str, Any] = {}
    condition: str | None = None
    doses: list[TherapyDoseInput] = []


class TherapyUpdateRequest(PharmaBaseModel):
    tracked_package_id: UUID | None = None
    medicine_entry_id: UUID | None = None
    person_id: UUID | None = None
    doctor_id: UUID | None = None
    start_date: datetime | None = None
    rrule: str | None = None
    importance: Literal["vital", "essential", "standard"] | None = None
    notification_level: Literal["normal", "alarm"] | None = None
    notifications_silenced: bool | None = None
    snooze_minutes: int | None = None
    clinical_rules: dict[str, Any] | None = None
    condition: str | None = None
    doses: list[TherapyDoseInput] | None = None
