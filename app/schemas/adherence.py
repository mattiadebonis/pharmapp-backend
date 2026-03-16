from app.schemas.base import PharmaBaseModel
from app.schemas.log import ActivityLogDTO
from app.schemas.medicine import TrackedMedicineDTO
from app.schemas.monitoring import MonitoringMeasurementDTO
from app.schemas.therapy import TherapyWithDosesDTO


class AdherenceSnapshotDTO(PharmaBaseModel):
    therapies: list[TherapyWithDosesDTO] = []
    intake_logs: list[ActivityLogDTO] = []
    medicines: list[TrackedMedicineDTO] = []
    purchase_logs: list[ActivityLogDTO] = []
    monitoring_measurements: list[MonitoringMeasurementDTO] = []
