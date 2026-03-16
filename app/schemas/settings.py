from datetime import datetime
from typing import Literal
from uuid import UUID

from app.schemas.base import PharmaBaseModel


class UserSettingsDTO(PharmaBaseModel):
    user_id: UUID
    catalog_country: Literal["it", "us"]
    business_country: Literal["it", "us"]
    day_threshold_stocks_alarm: int
    therapy_notification_level: Literal["normal", "alarm"]
    therapy_snooze_minutes: int
    manual_intake_registration: bool
    prescription_message_template: str | None = None
    grace_minutes: int
    notify_caregivers: bool
    notify_shared: bool
    created_at: datetime
    updated_at: datetime


class UserSettingsUpdateRequest(PharmaBaseModel):
    catalog_country: Literal["it", "us"] | None = None
    business_country: Literal["it", "us"] | None = None
    day_threshold_stocks_alarm: int | None = None
    therapy_notification_level: Literal["normal", "alarm"] | None = None
    therapy_snooze_minutes: int | None = None
    manual_intake_registration: bool | None = None
    prescription_message_template: str | None = None
    grace_minutes: int | None = None
    notify_caregivers: bool | None = None
    notify_shared: bool | None = None
