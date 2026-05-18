from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from app.schemas.base import PharmaBaseModel
from app.schemas.dosing_schedule import DosingScheduleDTO
from app.schemas.injection_site import InjectionSiteDTO
from app.schemas.prescription import PrescriptionDTO
from app.schemas.supply import SupplyDTO


# ---------------------------------------------------------------------------
# Inline schedule for bulk medication+schedule creation. Mirrors
# DosingScheduleCreateRequest minus the medication_id (filled server-side
# from the freshly-created medication).
# ---------------------------------------------------------------------------
class EmbeddedScheduleCreate(PharmaBaseModel):
    id: UUID | None = None
    schedule_type: Literal["scheduled", "as_needed", "cycle", "tapering"]
    times: list[dict[str, Any]] | None = None
    pills_per_dose: float | None = None
    max_per_day: int | None = None
    min_interval_hours: float | None = None
    condition: str | None = None
    cycle_days: int | None = None
    cycle_start_date: date | None = None
    tapering_steps: list[dict[str, Any]] | None = None
    variable_subtype: Literal["weekly", "tapering", "escalation"] | None = None
    rrule: str | None = None
    is_active: bool = True
    importance: Literal["vital", "essential", "standard"] = "standard"
    notification_level: Literal["normal", "alarm"] = "normal"
    snooze_minutes: int | None = None
    notifications_silenced: bool = False
    weekly_overrides: dict[str, float] | None = None
    format: Literal["compressa", "inalatore", "gocce", "altro"] | None = None
    daily_limit: int | None = None
    weekly_alert_threshold: int | None = None
    cycle_pattern: Literal["weekly", "biweekly", "every_n"] | None = None
    cycle_weekdays: list[int] | None = None
    notify_day_before: bool = False
    post_tapering_behavior: Literal["fine_terapia", "mantenimento"] | None = None
    late_threshold_minutes: int | None = None


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
MedicationCategory = Literal["farmaco", "otc", "integratore"]
TrackingMode = Literal["passive", "active"]


# ---------------------------------------------------------------------------
# DTO – full representation returned by the API
# ---------------------------------------------------------------------------
class MedicationDTO(PharmaBaseModel):
    id: UUID
    profile_id: UUID
    catalog_product_key: str | None = None
    catalog_country: str | None = None
    name: str
    principle: str | None = None
    color: str | None = None
    category: MedicationCategory | None = None
    start_date: date | None = None
    tracking_mode: TrackingMode = "passive"
    requires_prescription: bool = False
    is_paused: bool = False
    is_archived: bool = False
    shared_with_caregiver: bool = False
    image_url: str | None = None
    notes: str | None = None
    catalog_snapshot: dict[str, Any] | None = None
    prescribing_doctor_id: UUID | None = None
    managed_by_routine_id: UUID | None = None
    injection_sites: list[InjectionSiteDTO] = []
    anticipo_reminder: int | None = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Create request
# ---------------------------------------------------------------------------
class MedicationCreateRequest(PharmaBaseModel):
    id: UUID | None = None
    profile_id: UUID
    catalog_product_key: str | None = None
    catalog_country: str | None = None
    name: str
    principle: str | None = None
    color: str | None = None
    category: MedicationCategory | None = None
    start_date: date | None = None
    tracking_mode: TrackingMode = "passive"
    requires_prescription: bool = False
    is_paused: bool = False
    is_archived: bool = False
    shared_with_caregiver: bool = False
    image_url: str | None = None
    notes: str | None = None
    catalog_snapshot: dict[str, Any] | None = None
    prescribing_doctor_id: UUID | None = None
    injection_sites: list[InjectionSiteDTO] | None = None
    anticipo_reminder: int | None = None
    # Optional embedded schedules — when present, the create endpoint
    # also inserts each schedule with the new medication_id atomically.
    # Lets the iOS client persist a med + its dosing in a single round-trip.
    schedules: list[EmbeddedScheduleCreate] | None = None


# ---------------------------------------------------------------------------
# Update request
# ---------------------------------------------------------------------------
class MedicationUpdateRequest(PharmaBaseModel):
    profile_id: UUID | None = None
    catalog_product_key: str | None = None
    catalog_country: str | None = None
    name: str | None = None
    principle: str | None = None
    color: str | None = None
    category: MedicationCategory | None = None
    start_date: date | None = None
    tracking_mode: TrackingMode | None = None
    requires_prescription: bool | None = None
    is_paused: bool | None = None
    is_archived: bool | None = None
    shared_with_caregiver: bool | None = None
    image_url: str | None = None
    notes: str | None = None
    catalog_snapshot: dict[str, Any] | None = None
    prescribing_doctor_id: UUID | None = None
    injection_sites: list[InjectionSiteDTO] | None = None
    anticipo_reminder: int | None = None


# ---------------------------------------------------------------------------
# Composite DTO – medication with related details inline
# ---------------------------------------------------------------------------
class MedicationWithDetailsDTO(MedicationDTO):
    schedules: list[DosingScheduleDTO] = []
    supply: SupplyDTO | None = None
    prescriptions: list[PrescriptionDTO] = []
