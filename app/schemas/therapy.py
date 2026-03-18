from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import Field

from app.schemas.base import PharmaBaseModel


class TherapyDoseDTO(PharmaBaseModel):
    id: UUID
    therapy_id: UUID
    time_of_day: str = Field(validation_alias="time")  # HH:MM:SS format
    amount: float
    sort_order: int


class TherapyDTO(PharmaBaseModel):
    id: UUID
    tracked_medicine_id: UUID
    tracked_package_id: UUID | None = None
    medicine_entry_id: UUID | None = None
    person_id: UUID | None = None
    prescribing_doctor_id: UUID | None = Field(default=None, validation_alias="doctor_id")
    start_date: datetime
    rrule: str | None = None
    # Decomposed RRULE fields for iOS compatibility
    freq: str | None = None
    interval: int | None = None
    until: datetime | None = None
    count: int | None = None
    by_day: list[str] | None = None
    cycle_on_days: int | None = None
    cycle_off_days: int | None = None
    importance: Literal["vital", "essential", "standard"]
    notification_level: Literal["normal", "alarm"]
    notifications_silenced: bool
    snooze_minutes: int
    manual_intake: bool = False
    clinical_rules_json: dict[str, Any] = Field(default_factory=dict, validation_alias="clinical_rules")
    condition: str | None = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class TherapyWithDosesDTO(TherapyDTO):
    doses: list[TherapyDoseDTO] = []


class TherapyDoseInput(PharmaBaseModel):
    time: str = Field(validation_alias="time_of_day")  # iOS sends time_of_day, DB column is time
    amount: float


class TherapyCreateRequest(PharmaBaseModel):
    tracked_package_id: UUID | None = None
    medicine_entry_id: UUID | None = None
    person_id: UUID | None = None
    doctor_id: UUID | None = Field(default=None, validation_alias="prescribing_doctor_id")
    start_date: datetime
    rrule: str | None = None
    freq: str | None = None
    interval: int | None = None
    until: datetime | None = None
    count: int | None = None
    by_day: list[str] | None = None
    cycle_on_days: int | None = None
    cycle_off_days: int | None = None
    importance: Literal["vital", "essential", "standard"] = "standard"
    notification_level: Literal["normal", "alarm"] = "normal"
    notifications_silenced: bool = False
    snooze_minutes: int = 10
    manual_intake: bool = False
    clinical_rules: dict[str, Any] = Field(default_factory=dict, validation_alias="clinical_rules_json")
    condition: str | None = None
    is_active: bool = True
    doses: list[TherapyDoseInput] = []


class TherapyUpdateRequest(PharmaBaseModel):
    tracked_package_id: UUID | None = None
    medicine_entry_id: UUID | None = None
    person_id: UUID | None = None
    doctor_id: UUID | None = Field(default=None, validation_alias="prescribing_doctor_id")
    start_date: datetime | None = None
    rrule: str | None = None
    freq: str | None = None
    interval: int | None = None
    until: datetime | None = None
    count: int | None = None
    by_day: list[str] | None = None
    cycle_on_days: int | None = None
    cycle_off_days: int | None = None
    importance: Literal["vital", "essential", "standard"] | None = None
    notification_level: Literal["normal", "alarm"] | None = None
    notifications_silenced: bool | None = None
    snooze_minutes: int | None = None
    manual_intake: bool | None = None
    clinical_rules: dict[str, Any] | None = Field(default=None, validation_alias="clinical_rules_json")
    condition: str | None = None
    is_active: bool | None = None
    doses: list[TherapyDoseInput] | None = None
