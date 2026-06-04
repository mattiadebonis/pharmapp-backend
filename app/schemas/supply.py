from datetime import date, datetime
from uuid import UUID

from pydantic import ConfigDict

from app.schemas.base import PharmaBaseModel


# ---------------------------------------------------------------------------
# DTO – full representation returned by the API
# ---------------------------------------------------------------------------
class SupplyDTO(PharmaBaseModel):
    id: UUID
    medication_id: UUID
    pills_at_purchase: float | None = None
    current_pills: float | None = None
    purchase_date: date | None = None
    refill_threshold_days: int | None = None
    package_units: int | None = None
    package_label: str | None = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Create request
# ---------------------------------------------------------------------------
class SupplyCreateRequest(PharmaBaseModel):
    medication_id: UUID
    pills_at_purchase: float | None = None
    current_pills: float | None = None
    purchase_date: date | None = None
    refill_threshold_days: int | None = None
    package_units: int | None = None
    package_label: str | None = None


# ---------------------------------------------------------------------------
# Update request
# ---------------------------------------------------------------------------
class SupplyUpdateRequest(PharmaBaseModel):
    # Allow legacy iOS clients to send `medication_id` in the body without
    # tripping the global `extra="forbid"`. The router takes the medication
    # from the path; the service drops any body value before writing.
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, extra="ignore")

    pills_at_purchase: float | None = None
    current_pills: float | None = None
    purchase_date: date | None = None
    refill_threshold_days: int | None = None
    package_units: int | None = None
    package_label: str | None = None
