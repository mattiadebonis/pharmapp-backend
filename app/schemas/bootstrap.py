from app.schemas.base import PharmaBaseModel
from app.schemas.caregiver import CaregiverRelationDTO, PendingChangeDTO
from app.schemas.doctor import DoctorDTO
from app.schemas.dose_event import DoseEventDTO
from app.schemas.medication import MedicationWithDetailsDTO
from app.schemas.parameter import ParameterDTO
from app.schemas.prescription_request import PrescriptionRequestDTO
from app.schemas.profile import ProfileDTO
from app.schemas.routine import RoutineWithStepsDTO
from app.schemas.settings import UserSettingsDTO
from app.schemas.subscription import SubscriptionStateDTO


class BootstrapResponse(PharmaBaseModel):
    """All data needed for offline-first client sync in a single payload.

    NB: activity_logs / device_tokens / recent_measurements sono stati
    rimossi dal payload: il client iOS non li ha mai decodificati.
    Measurements on-demand via /v2/measurements; audit via /v2/me/access-log.
    """

    profiles: list[ProfileDTO] = []
    medications: list[MedicationWithDetailsDTO] = []
    doctors: list[DoctorDTO] = []
    settings: UserSettingsDTO | None = None
    subscription: SubscriptionStateDTO | None = None
    dose_events: list[DoseEventDTO] = []
    caregiver_relations: list[CaregiverRelationDTO] = []
    pending_changes: list[PendingChangeDTO] = []
    prescription_requests: list[PrescriptionRequestDTO] = []
    routines: list[RoutineWithStepsDTO] = []
    parameters: list[ParameterDTO] = []
