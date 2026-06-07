from datetime import date, datetime
from uuid import UUID

from pydantic import Field

from app.schemas.base import PharmaBaseModel


# ---------------------------------------------------------------------------
# DTO – full representation returned by the API / bootstrap
# ---------------------------------------------------------------------------
class MedicationPackageDTO(PharmaBaseModel):
    id: UUID
    medication_id: UUID
    strength_text: str = ""
    strength_mg: float | None = None
    forma: str | None = None
    dose_format: str | None = None
    units_per_box: int = 1
    box_count: int = 1
    current_units: float = 0
    refill_threshold_days: int = 7
    purchase_date: date | None = None
    package_label: str | None = None
    catalog_package_id: str | None = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Inline package for bulk medication+packages creation (mirror del create
# request senza medication_id, riempito server-side). Una per dosaggio.
#
# Le regole (units_per_box >= 1, gli altri >= 0) sono espresse come vincoli
# `Field` invece che come validator custom: producono errori 422 con ctx
# JSON-serializzabile, mentre un `ValueError` sollevato in un validator
# romperebbe l'handler di validazione (che serializza `exc.errors()`).
# ---------------------------------------------------------------------------
class EmbeddedPackageCreate(PharmaBaseModel):
    id: UUID | None = None
    strength_text: str = ""
    strength_mg: float | None = Field(default=None, ge=0)
    forma: str | None = None
    dose_format: str | None = None
    units_per_box: int = Field(default=1, ge=1)
    box_count: int = Field(default=1, ge=0)
    current_units: float = Field(default=0, ge=0)
    refill_threshold_days: int = Field(default=7, ge=0)
    purchase_date: date | None = None
    package_label: str | None = None
    catalog_package_id: str | None = None


# ---------------------------------------------------------------------------
# Replace request — sostituisce l'intero set di confezioni di un farmaco.
# Il client iOS invia tutte le confezioni correnti; il server fa replace.
# ---------------------------------------------------------------------------
class PackagesReplaceRequest(PharmaBaseModel):
    packages: list[EmbeddedPackageCreate] = []
