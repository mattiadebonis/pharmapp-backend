from datetime import date, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BeforeValidator, Field, field_validator

from app.schemas.base import PharmaBaseModel

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
ScheduleType = Literal["scheduled", "as_needed", "cycle", "tapering"]
VariableSubtype = Literal["weekly", "tapering", "escalation"]
Importance = Literal["vital", "essential", "standard"]
NotificationLevel = Literal["normal", "alarm"]
# Allineato all'enum iOS DoseFormat (12 case): l'app invia il rawValue raw.
DoseFormat = Literal[
    "compressa", "capsula", "granuli", "gocce", "sciroppo", "iniettabile",
    "inalatore", "cerotto", "collirio", "crema", "supposta", "altro",
]
CyclePattern = Literal["weekly", "biweekly", "every_n"]
PostTaperingBehavior = Literal["fine_terapia", "mantenimento", "ripeti"]


# ---------------------------------------------------------------------------
# Per-day dose composition (weekly_overrides)
# ---------------------------------------------------------------------------
class DoseComponentSchema(PharmaBaseModel):
    """Un componente di dose: `units` compresse di un certo dosaggio (mg)."""

    units: float = Field(default=0, ge=0)
    strength_mg: float | None = Field(default=None, ge=0)
    strength_text: str | None = None


def _normalize_weekly_overrides(v: Any) -> Any:
    """Normalizza i 3 formati di `weekly_overrides` (per giorno) a lista di
    componenti: numero legacy → [{units}]; oggetto singolo → [obj]; lista →
    passthrough. Mantiene la retro-compatibilità con i dati DB esistenti.
    """
    if not isinstance(v, dict):
        return v
    out: dict[str, Any] = {}
    for key, val in v.items():
        if isinstance(val, bool):
            out[key] = []
        elif isinstance(val, (int, float)):
            out[key] = [{"units": float(val)}]
        elif isinstance(val, dict):
            out[key] = [val]
        elif isinstance(val, list):
            out[key] = val
        else:
            out[key] = []
    return out


# weekday (string "1"–"7", Calendar: 1=Sun…7=Sat) → lista di componenti dose.
# Accetta anche la shape legacy (numero = unità) via BeforeValidator.
WeeklyOverrides = Annotated[
    dict[str, list[DoseComponentSchema]],
    BeforeValidator(_normalize_weekly_overrides),
]


# ---------------------------------------------------------------------------
# DTO – full representation returned by the API
# ---------------------------------------------------------------------------
class DosingScheduleDTO(PharmaBaseModel):
    id: UUID
    medication_id: UUID
    schedule_type: ScheduleType
    # times: [{time, label?, preposto?}]
    times: list[dict[str, Any]] | None = None
    pills_per_dose: float | None = None
    max_per_day: int | None = None
    min_interval_hours: float | None = None
    condition: str | None = None
    cycle_days: int | None = None
    cycle_start_date: date | None = None
    tapering_steps: list[dict[str, Any]] | None = None
    variable_subtype: VariableSubtype | None = None
    rrule: str | None = None
    is_active: bool = True
    importance: Importance = "standard"
    notification_level: NotificationLevel = "alarm"
    snooze_minutes: int | None = None
    notifications_silenced: bool = False
    # weekday (string "1"–"7", Calendar: 1=Sun…7=Sat) → pills_per_dose override.
    # A value of 0 means skip that day (no event, no notification).
    weekly_overrides: WeeklyOverrides | None = None
    # Redesigned "Quando lo prendi" fields (migration 008)
    format: DoseFormat | None = None
    daily_limit: int | None = None
    weekly_alert_threshold: int | None = None
    cycle_pattern: CyclePattern | None = None
    cycle_weekdays: list[int] | None = None
    # Durata totale del ciclo in settimane (es. rotazione siti iniezione).
    # Pass-through: scritto e letto da iOS (cycleTotalWeeks).
    cycle_total_weeks: int | None = None
    notify_day_before: bool = False
    post_tapering_behavior: PostTaperingBehavior | None = None
    # Soglia in minuti oltre due_at per classificare la dose come "ritardo".
    # NULL → 30 min (default applicativo, vedi adherence_service).
    late_threshold_minutes: int | None = None
    # Dosaggio (strength) per unità, scelto in Posologia. La dose totale di
    # un'assunzione = pills_per_dose (unità) × strength_mg (mg per unità).
    strength_mg: float | None = None
    strength_text: str | None = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Create request
# ---------------------------------------------------------------------------
class DosingScheduleCreateRequest(PharmaBaseModel):
    medication_id: UUID
    schedule_type: ScheduleType
    times: list[dict[str, Any]] | None = None
    pills_per_dose: float | None = None
    max_per_day: int | None = None
    min_interval_hours: float | None = None
    condition: str | None = None
    cycle_days: int | None = None
    cycle_start_date: date | None = None
    tapering_steps: list[dict[str, Any]] | None = None
    variable_subtype: VariableSubtype | None = None
    rrule: str | None = None
    is_active: bool = True
    importance: Importance = "standard"
    notification_level: NotificationLevel = "alarm"
    snooze_minutes: int | None = None
    notifications_silenced: bool = False
    weekly_overrides: WeeklyOverrides | None = None
    format: DoseFormat | None = None
    daily_limit: int | None = None
    weekly_alert_threshold: int | None = None
    cycle_pattern: CyclePattern | None = None
    cycle_weekdays: list[int] | None = None
    # Durata totale del ciclo in settimane (es. rotazione siti iniezione).
    # Pass-through: scritto e letto da iOS (cycleTotalWeeks).
    cycle_total_weeks: int | None = None
    notify_day_before: bool = False
    post_tapering_behavior: PostTaperingBehavior | None = None
    late_threshold_minutes: int | None = None
    strength_mg: float | None = None
    strength_text: str | None = None

    @field_validator("strength_mg")
    @classmethod
    def _strength_mg_non_negative(cls, v: float | None) -> float | None:
        if v is not None and v < 0:
            raise ValueError("strength_mg must be >= 0")
        return v

    @field_validator("pills_per_dose")
    @classmethod
    def _pills_per_dose_positive(cls, v: float | None) -> float | None:
        if v is not None and v <= 0:
            raise ValueError("pills_per_dose must be > 0")
        return v


# ---------------------------------------------------------------------------
# Update request
# ---------------------------------------------------------------------------
class DosingScheduleUpdateRequest(PharmaBaseModel):
    schedule_type: ScheduleType | None = None
    times: list[dict[str, Any]] | None = None
    pills_per_dose: float | None = None
    max_per_day: int | None = None
    min_interval_hours: float | None = None
    condition: str | None = None
    cycle_days: int | None = None
    cycle_start_date: date | None = None
    tapering_steps: list[dict[str, Any]] | None = None
    variable_subtype: VariableSubtype | None = None
    rrule: str | None = None
    is_active: bool | None = None
    importance: Importance | None = None
    notification_level: NotificationLevel | None = None
    snooze_minutes: int | None = None
    notifications_silenced: bool | None = None
    weekly_overrides: WeeklyOverrides | None = None
    format: DoseFormat | None = None
    daily_limit: int | None = None
    weekly_alert_threshold: int | None = None
    cycle_pattern: CyclePattern | None = None
    cycle_weekdays: list[int] | None = None
    cycle_total_weeks: int | None = None
    notify_day_before: bool | None = None
    post_tapering_behavior: PostTaperingBehavior | None = None
    late_threshold_minutes: int | None = None
    strength_mg: float | None = None
    strength_text: str | None = None

    @field_validator("strength_mg")
    @classmethod
    def _strength_mg_non_negative(cls, v: float | None) -> float | None:
        if v is not None and v < 0:
            raise ValueError("strength_mg must be >= 0")
        return v
