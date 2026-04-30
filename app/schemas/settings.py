from datetime import datetime
from typing import Literal
from uuid import UUID

from app.schemas.base import PharmaBaseModel


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
TrackingMode = Literal["passive", "active"]


# ---------------------------------------------------------------------------
# DTO – full representation returned by the API
# ---------------------------------------------------------------------------
class UserSettingsDTO(PharmaBaseModel):
    user_id: UUID
    catalog_country: str | None = None
    default_refill_threshold: int | None = None
    default_tracking_mode: TrackingMode = "passive"
    default_snooze_minutes: int = 10
    grace_minutes: int = 120
    notify_caregivers: bool = True
    notifications_enabled: bool = True
    refill_alerts_enabled: bool = True
    biometrics_enabled: bool = False
    face_id_sensitive_actions: bool = False
    anonymous_notifications: bool = False
    hide_medication_names: bool = False
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Update request – every field optional
# ---------------------------------------------------------------------------
class UserSettingsUpdateRequest(PharmaBaseModel):
    catalog_country: str | None = None
    default_refill_threshold: int | None = None
    default_tracking_mode: TrackingMode | None = None
    default_snooze_minutes: int | None = None
    grace_minutes: int | None = None
    notify_caregivers: bool | None = None
    notifications_enabled: bool | None = None
    refill_alerts_enabled: bool | None = None
    biometrics_enabled: bool | None = None
    face_id_sensitive_actions: bool | None = None
    anonymous_notifications: bool | None = None
    hide_medication_names: bool | None = None
