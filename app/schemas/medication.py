from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from app.schemas.base import PharmaBaseModel
from app.schemas.dosing_schedule import DosingScheduleDTO
from app.schemas.injection_site import InjectionSiteDTO
from app.schemas.prescription import PrescriptionDTO
from app.schemas.supply import SupplyDTO


# ---------------------------------------------------------------------------
# Inline supply for bulk medication+supply creation. Specchio di
# SupplyCreateRequest senza medication_id (filled server-side dopo aver
# creato la medication).
# ---------------------------------------------------------------------------
class EmbeddedSupplyCreate(PharmaBaseModel):
    pills_at_purchase: float | None = None
    current_pills: float | None = None
    purchase_date: "date | None" = None
    refill_threshold_days: int | None = None
    package_units: int | None = None
    package_label: str | None = None


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
    notification_level: Literal["normal", "alarm"] = "alarm"
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
Criticality = Literal["none", "critical"]


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
    # Today v2 — flag clinico per badge "Critico" sulla card temporale.
    # Default 'none'; 'critical' attiva badge rosso + variant scoring.
    criticality: Criticality | None = "none"
    # Today v2 — timestamp di sospensione decisa dal medico. Distinto da
    # `is_paused` (pausa utente). Quando != null la dose non entra in
    # timeline e contribuisce al banner "Sospesa dal medico · N farmaci".
    suspended_by_doctor_at: datetime | None = None
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
    criticality: Criticality | None = "none"
    suspended_by_doctor_at: datetime | None = None
    # Optional embedded schedules — when present, the create endpoint
    # also inserts each schedule with the new medication_id atomically.
    # Lets the iOS client persist a med + its dosing in a single round-trip.
    schedules: list[EmbeddedScheduleCreate] | None = None
    # Optional embedded supply — same pattern: il client compila scorte
    # nel wizard, il backend crea anche la riga `supplies` linkata.
    # Senza questo, il bootstrap risponderebbe con supply=null al
    # prossimo refresh e iOS mostrerebbe "scorte non gestite".
    supply: EmbeddedSupplyCreate | None = None


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
    criticality: Criticality | None = None
    suspended_by_doctor_at: datetime | None = None


# ---------------------------------------------------------------------------
# Composite DTO – medication with related details inline
# ---------------------------------------------------------------------------
class MedicationWithDetailsDTO(MedicationDTO):
    schedules: list[DosingScheduleDTO] = []
    supply: SupplyDTO | None = None
    prescriptions: list[PrescriptionDTO] = []
