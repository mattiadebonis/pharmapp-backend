from app.schemas.activity_log import ActivityLogDTO
from app.schemas.base import PharmaBaseModel
from app.schemas.caregiver import CaregiverRelationDTO, PendingChangeDTO
from app.schemas.device_token import DeviceTokenDTO
from app.schemas.doctor import DoctorDTO
from app.schemas.dose_event import DoseEventDTO
from app.schemas.measurement import MeasurementDTO
from app.schemas.medication import MedicationWithDetailsDTO
from app.schemas.parameter import ParameterDTO
from app.schemas.prescription_request import PrescriptionRequestDTO
from app.schemas.profile import ProfileDTO
from app.schemas.routine import RoutineWithStepsDTO
from app.schemas.settings import UserSettingsDTO
from app.schemas.subscription import SubscriptionStateDTO


class BootstrapResponse(PharmaBaseModel):
    """All data needed for offline-first client sync in a single payload."""

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
    recent_measurements: list[MeasurementDTO] = []
    activity_logs: list[ActivityLogDTO] = []
    device_tokens: list[DeviceTokenDTO] = []
