# ---------------------------------------------------------------------------
# app/schemas – Pydantic schemas for PharmaApp backend
# ---------------------------------------------------------------------------

from app.schemas.base import (
    PharmaBaseModel,
)
from app.schemas.bootstrap import (
    BootstrapResponse,
)
from app.schemas.caregiver import (
    CaregiverAcceptRequest,
    CaregiverInviteRequest,
    CaregiverRelationDTO,
    PendingChangeDTO,
)
from app.schemas.catalog import (
    CatalogPackageDTO,
    CatalogProductDTO,
    CatalogSearchResultDTO,
)
from app.schemas.device_token import (
    DeviceTokenCreateRequest,
    DeviceTokenDTO,
)
from app.schemas.doctor import (
    DoctorCreateRequest,
    DoctorDTO,
    DoctorUpdateRequest,
)
from app.schemas.dose_event import (
    DoseEventCreateRequest,
    DoseEventDTO,
)
from app.schemas.dosing_schedule import (
    DosingScheduleDTO,
    DosingScheduleUpdateRequest,
)
from app.schemas.medication import (
    MedicationCreateRequest,
    MedicationDTO,
    MedicationUpdateRequest,
    MedicationWithDetailsDTO,
)
from app.schemas.prescription import (
    PrescriptionCreateRequest,
    PrescriptionDTO,
    PrescriptionUpdateRequest,
)
from app.schemas.profile import (
    ProfileDTO,
    ProfileUpdateRequest,
)
from app.schemas.settings import (
    UserSettingsDTO,
    UserSettingsUpdateRequest,
)
from app.schemas.supply import (
    SupplyCreateRequest,
    SupplyDTO,
    SupplyUpdateRequest,
)

__all__ = [
    # base
    "PharmaBaseModel",
    # profile
    "ProfileDTO",
    "ProfileUpdateRequest",
    # doctor
    "DoctorDTO",
    "DoctorCreateRequest",
    "DoctorUpdateRequest",
    # medication
    "MedicationDTO",
    "MedicationCreateRequest",
    "MedicationUpdateRequest",
    "MedicationWithDetailsDTO",
    # dosing_schedule
    "DosingScheduleDTO",
    "DosingScheduleUpdateRequest",
    # supply
    "SupplyDTO",
    "SupplyCreateRequest",
    "SupplyUpdateRequest",
    # prescription
    "PrescriptionDTO",
    "PrescriptionCreateRequest",
    "PrescriptionUpdateRequest",
    # dose_event
    "DoseEventDTO",
    "DoseEventCreateRequest",
    # caregiver
    "CaregiverRelationDTO",
    "CaregiverInviteRequest",
    "CaregiverAcceptRequest",
    "PendingChangeDTO",
    # device_token
    "DeviceTokenDTO",
    "DeviceTokenCreateRequest",
    # settings
    "UserSettingsDTO",
    "UserSettingsUpdateRequest",
    # bootstrap
    "BootstrapResponse",
    # catalog
    "CatalogSearchResultDTO",
    "CatalogProductDTO",
    "CatalogPackageDTO",
]
