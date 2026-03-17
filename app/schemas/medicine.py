from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from app.schemas.base import PharmaBaseModel


class TrackedMedicineDTO(PharmaBaseModel):
    id: UUID
    owner_user_id: UUID
    cabinet_id: UUID | None = None
    catalog_country: str | None = None
    catalog_source: str | None = None
    catalog_product_id: str | None = Field(default=None, validation_alias="catalog_product_key")
    catalog_family_key: str | None = None
    display_name: str = Field(validation_alias="name")
    generic_name: str | None = None
    principle: str | None = None
    requires_prescription: bool
    labels: list[str] = []
    custom_stock_threshold: int | None = None
    manual_intake_registration: bool = False
    image_url: str | None = None
    catalog_snapshot: dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime


class TrackedPackageDTO(PharmaBaseModel):
    id: UUID
    tracked_medicine_id: UUID
    catalog_country: str | None = None
    catalog_source: str | None = None
    catalog_package_id: str | None = Field(default=None, validation_alias="catalog_package_key")
    catalog_code: str | None = None
    package_label: str | None = None
    form_type: str | None = Field(default=None, validation_alias="tipologia")
    units_per_package: int = 1
    dosage_value: float | None = Field(default=None, validation_alias="unit_value")
    dosage_unit: str | None = Field(default=None, validation_alias="unit_name")
    volume: str | None = None
    package_snapshot: dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime


class TrackedMedicineWithPackagesDTO(PharmaBaseModel):
    """Medicine with its packages inline."""

    id: UUID
    owner_user_id: UUID
    cabinet_id: UUID | None = None
    catalog_country: str | None = None
    catalog_source: str | None = None
    catalog_product_id: str | None = Field(default=None, validation_alias="catalog_product_key")
    catalog_family_key: str | None = None
    display_name: str = Field(validation_alias="name")
    generic_name: str | None = None
    principle: str | None = None
    requires_prescription: bool
    labels: list[str] = []
    custom_stock_threshold: int | None = None
    manual_intake_registration: bool = False
    image_url: str | None = None
    catalog_snapshot: dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime
    packages: list[TrackedPackageDTO] = []


class CreateMedicineFromCatalogRequest(PharmaBaseModel):
    cabinet_id: UUID | None = None
    catalog_country: str
    catalog_source: str
    catalog_product_key: str = Field(validation_alias="catalog_product_id")
    catalog_family_key: str | None = None
    name: str = Field(validation_alias="display_name")
    principle: str | None = None
    requires_prescription: bool = False
    labels: list[str] = []
    custom_stock_threshold: int = 0
    manual_intake_registration: bool = False
    catalog_snapshot: dict[str, Any] = {}
    # Package data
    catalog_package_key: str = Field(validation_alias="catalog_package_id")
    catalog_code: str | None = None
    tipologia: str | None = Field(default=None, validation_alias="form_type")
    units_per_package: int = 1
    unit_value: float | None = Field(default=None, validation_alias="dosage_value")
    unit_name: str | None = Field(default=None, validation_alias="dosage_unit")
    volume: str | None = None
    package_snapshot: dict[str, Any] = {}


class MedicineUpdateRequest(PharmaBaseModel):
    name: str | None = Field(default=None, validation_alias="display_name")
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
    catalog_package_key: str = Field(validation_alias="catalog_package_id")
    catalog_code: str | None = None
    tipologia: str | None = Field(default=None, validation_alias="form_type")
    units_per_package: int = 1
    unit_value: float | None = Field(default=None, validation_alias="dosage_value")
    unit_name: str | None = Field(default=None, validation_alias="dosage_unit")
    volume: str | None = None
    package_snapshot: dict[str, Any] = {}
