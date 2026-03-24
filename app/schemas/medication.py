from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from app.schemas.base import PharmaBaseModel
from app.schemas.dosing_schedule import DosingScheduleDTO
from app.schemas.prescription import PrescriptionDTO
from app.schemas.supply import SupplyDTO


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
    tracking_mode: TrackingMode = "passive"
    requires_prescription: bool = False
    is_paused: bool = False
    is_archived: bool = False
    shared_with_caregiver: bool = False
    image_url: str | None = None
    notes: str | None = None
    catalog_snapshot: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Create request
# ---------------------------------------------------------------------------
class MedicationCreateRequest(PharmaBaseModel):
    profile_id: UUID
    catalog_product_key: str | None = None
    catalog_country: str | None = None
    name: str
    principle: str | None = None
    color: str | None = None
    category: MedicationCategory | None = None
    tracking_mode: TrackingMode = "passive"
    requires_prescription: bool = False
    is_paused: bool = False
    is_archived: bool = False
    shared_with_caregiver: bool = False
    image_url: str | None = None
    notes: str | None = None
    catalog_snapshot: dict[str, Any] | None = None


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
    tracking_mode: TrackingMode | None = None
    requires_prescription: bool | None = None
    is_paused: bool | None = None
    is_archived: bool | None = None
    shared_with_caregiver: bool | None = None
    image_url: str | None = None
    notes: str | None = None
    catalog_snapshot: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Composite DTO – medication with related details inline
# ---------------------------------------------------------------------------
class MedicationWithDetailsDTO(MedicationDTO):
    schedules: list[DosingScheduleDTO] = []
    supply: SupplyDTO | None = None
    prescriptions: list[PrescriptionDTO] = []
