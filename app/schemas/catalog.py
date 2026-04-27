from typing import Any

from pydantic import Field

from app.schemas.base import PharmaBaseModel


class CatalogSearchResultDTO(PharmaBaseModel):
    country: str
    source: str
    product_id: str
    package_id: str
    family_id: str | None = None
    display_name: str
    brand_name: str | None = None
    generic_name: str | None = None
    principle: str | None = None
    manufacturer_name: str | None = None
    requires_prescription: bool
    package_label: str | None = None
    units_per_package: int = Field(validation_alias="units")
    form_type: str | None = Field(default=None, validation_alias="tipologia")
    dosage_value: int = Field(default=0, validation_alias="valore")
    dosage_unit: str = Field(default="", validation_alias="unita")
    strength_text: str | None = None
    volume: str = ""
    availability: str
    catalog_code: str | None = None
    catalog_snapshot: dict[str, Any] = {}
    # New fields from CSV
    link_fi: str | None = None
    link_rcp: str | None = None
    fornitura_code: str | None = None
    codice_atc: str | None = None
    is_homeopathic: bool | None = None


class CatalogProductDTO(PharmaBaseModel):
    id: str
    country: str
    source: str
    source_product_id: str
    family_id: str | None = None
    display_name: str
    brand_name: str | None = None
    generic_name: str | None = None
    active_ingredients: list[dict[str, Any]] = []
    dosage_form: str | None = None
    routes: list[str] = []
    strength_text: str | None = None
    manufacturer_name: str | None = None
    requires_prescription: bool | None = None
    availability: str
    atc_codes: list[str] = []
    regulatory: dict[str, Any] = {}
    packages: list[dict[str, Any]] = []
    source_meta: dict[str, Any] | None = None
    # New fields from CSV
    link_fi: str | None = None
    link_rcp: str | None = None
    fornitura_code: str | None = None
    codice_atc: str | None = None
    is_homeopathic: bool | None = None
    forme_distinte: list[str] = []


class CatalogPackageDTO(PharmaBaseModel):
    id: str
    source_package_id: str
    package_code: str | None = None
    display_name: str | None = None
    unit_count: int | None = None
    package_type: str | None = None
    volume_value: float | None = None
    volume_unit: str | None = None
    strength_text: str | None = None
    marketed: bool | None = None
    marketing_start_date: str | None = None
    marketing_end_date: str | None = None
    is_sample: bool | None = None
    requires_prescription: bool | None = None
    reimbursement_class: str | None = None
    reimbursement_text: str | None = None
    shortage_reason: str | None = None
    shortage_start_date: str | None = None
    shortage_end_date: str | None = None
    availability: str | None = None
    source_meta: dict[str, Any] | None = None
    # New fields from CSV
    fornitura: str | None = None
    fornitura_code: str | None = None
    codice_atc: str | None = None
    forma: str | None = None
    intake_method: str | None = None
