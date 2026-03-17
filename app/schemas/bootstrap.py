from pydantic import Field

from app.schemas.base import PharmaBaseModel
from app.schemas.cabinet import CabinetDTO, CabinetMembershipDTO
from app.schemas.custom_filter import CustomFilterDTO
from app.schemas.doctor import DoctorDTO
from app.schemas.dose_event import DoseEventDTO
from app.schemas.entry import MedicineEntryDTO
from app.schemas.log import ActivityLogDTO
from app.schemas.medicine import TrackedMedicineDTO, TrackedPackageDTO
from app.schemas.monitoring import MonitoringMeasurementDTO
from app.schemas.person import PersonDTO
from app.schemas.profile import ProfileDTO
from app.schemas.settings import UserSettingsDTO
from app.schemas.stock import StockDTO
from app.schemas.therapy import TherapyWithDosesDTO


class NotificationLockDTO(PharmaBaseModel):
    id: str
    cabinet_id: str
    device_id: str = Field(validation_alias="lock_key")
    expires_at: str | None = None
    locked_at: str = Field(validation_alias="created_at")


class BootstrapResponse(PharmaBaseModel):
    profile: ProfileDTO
    settings: UserSettingsDTO
    people: list[PersonDTO] = []
    doctors: list[DoctorDTO] = []
    cabinets: list[CabinetDTO] = []
    cabinet_memberships: list[CabinetMembershipDTO] = []
    tracked_medicines: list[TrackedMedicineDTO] = []
    tracked_packages: list[TrackedPackageDTO] = []
    medicine_entries: list[MedicineEntryDTO] = []
    therapies: list[TherapyWithDosesDTO] = []
    stocks: list[StockDTO] = []
    activity_logs: list[ActivityLogDTO] = []
    dose_events: list[DoseEventDTO] = []
    monitoring_measurements: list[MonitoringMeasurementDTO] = []
    custom_filters: list[CustomFilterDTO] = []
    notification_locks: list[NotificationLockDTO] = []
