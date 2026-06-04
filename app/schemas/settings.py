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
    default_tracking_mode: TrackingMode = "passive"
    grace_minutes: int = 120
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
    default_tracking_mode: TrackingMode | None = None
    grace_minutes: int | None = None
    biometrics_enabled: bool | None = None
    face_id_sensitive_actions: bool | None = None
    anonymous_notifications: bool | None = None
    hide_medication_names: bool | None = None
