from app.schemas.base import PharmaBaseModel
from app.schemas.caregiver import CaregiverRelationDTO, PendingChangeDTO
from app.schemas.doctor import DoctorDTO
from app.schemas.dose_event import DoseEventDTO
from app.schemas.medication import MedicationWithDetailsDTO
from app.schemas.prescription_request import PrescriptionRequestDTO
from app.schemas.profile import ProfileDTO
from app.schemas.settings import UserSettingsDTO


class BootstrapResponse(PharmaBaseModel):
    """All data needed for offline-first client sync in a single payload."""

    profiles: list[ProfileDTO] = []
    medications: list[MedicationWithDetailsDTO] = []
    doctors: list[DoctorDTO] = []
    settings: UserSettingsDTO | None = None
    dose_events: list[DoseEventDTO] = []
    caregiver_relations: list[CaregiverRelationDTO] = []
    pending_changes: list[PendingChangeDTO] = []
    prescription_requests: list[PrescriptionRequestDTO] = []
