from datetime import datetime
from typing import Any
from uuid import UUID

from app.schemas.base import PharmaBaseModel


class TrackedMedicineDTO(PharmaBaseModel):
    id: UUID
    owner_user_id: UUID
    cabinet_id: UUID | None = None
    catalog_country: str
    catalog_source: str
    catalog_product_key: str
    catalog_family_key: str | None = None
    name: str
    principle: str | None = None
    requires_prescription: bool
    labels: list[str] = []
    custom_stock_threshold: int
    manual_intake_registration: bool
    catalog_snapshot: dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime


class TrackedPackageDTO(PharmaBaseModel):
    id: UUID
    tracked_medicine_id: UUID
    catalog_country: str
    catalog_source: str
    catalog_package_key: str
    catalog_code: str | None = None
    tipologia: str | None = None
    units_per_package: int
    unit_value: float | None = None
    unit_name: str | None = None
    volume: str | None = None
    package_snapshot: dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime


class TrackedMedicineWithPackagesDTO(PharmaBaseModel):
    """Medicine with its packages inline."""

    id: UUID
    owner_user_id: UUID
    cabinet_id: UUID | None = None
    catalog_country: str
    catalog_source: str
    catalog_product_key: str
    catalog_family_key: str | None = None
    name: str
    principle: str | None = None
    requires_prescription: bool
    labels: list[str] = []
    custom_stock_threshold: int
    manual_intake_registration: bool
    catalog_snapshot: dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime
    packages: list[TrackedPackageDTO] = []


class CreateMedicineFromCatalogRequest(PharmaBaseModel):
    cabinet_id: UUID | None = None
    catalog_country: str
    catalog_source: str
    catalog_product_key: str
    catalog_family_key: str | None = None
    name: str
    principle: str | None = None
    requires_prescription: bool = False
    labels: list[str] = []
    custom_stock_threshold: int = 0
    manual_intake_registration: bool = False
    catalog_snapshot: dict[str, Any] = {}
    # Package data
    catalog_package_key: str
    catalog_code: str | None = None
    tipologia: str | None = None
    units_per_package: int = 1
    unit_value: float | None = None
    unit_name: str | None = None
    volume: str | None = None
    package_snapshot: dict[str, Any] = {}


class MedicineUpdateRequest(PharmaBaseModel):
    name: str | None = None
    principle: str | None = None
    requires_prescription: bool | None = None
    manual_intake_registration: bool | None = None


class LabelsUpdateRequest(PharmaBaseModel):
    labels: list[str]


class StockThresholdUpdateRequest(PharmaBaseModel):
    custom_stock_threshold: int


class CabinetMoveRequest(PharmaBaseModel):
    cabinet_id: UUID | None = None


class PackageCreateRequest(PharmaBaseModel):
    catalog_country: str
    catalog_source: str
    catalog_package_key: str
    catalog_code: str | None = None
    tipologia: str | None = None
    units_per_package: int = 1
    unit_value: float | None = None
    unit_name: str | None = None
    volume: str | None = None
    package_snapshot: dict[str, Any] = {}
