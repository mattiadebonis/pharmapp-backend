from datetime import datetime
from uuid import UUID

from supabase import Client

from app.schemas.adherence import AdherenceSnapshotDTO
from app.schemas.log import ActivityLogDTO
from app.schemas.medicine import TrackedMedicineDTO
from app.schemas.monitoring import MonitoringMeasurementDTO
from app.schemas.therapy import TherapyWithDosesDTO


async def get_adherence(supabase: Client, user_id: UUID, since: datetime, until: datetime) -> AdherenceSnapshotDTO:
    """Aggregate adherence data for a time window."""
    uid = str(user_id)
    since_iso = since.isoformat()
    until_iso = until.isoformat()

    # Get user's medicines
    meds_r = supabase.table("tracked_medicines").select("*").eq("owner_user_id", uid).execute()
    if not meds_r.data:
        return AdherenceSnapshotDTO()

    med_ids = [m["id"] for m in meds_r.data]

    # Therapies with doses
    therapies_r = supabase.table("therapies").select("*").in_("tracked_medicine_id", med_ids).execute()
    therapy_ids = [t["id"] for t in therapies_r.data]
    if therapy_ids:
        doses_r = (
            supabase.table("therapy_doses")
            .select("*")
            .in_("therapy_id", therapy_ids)
            .order("sort_order")
            .execute()
        )
    else:
        doses_r = type("R", (), {"data": []})()

    doses_by_therapy: dict[str, list] = {}
    for d in doses_r.data:
        doses_by_therapy.setdefault(d["therapy_id"], []).append(d)

    therapies = [
        TherapyWithDosesDTO.model_validate({**t, "doses": doses_by_therapy.get(t["id"], [])})
        for t in therapies_r.data
    ]

    # Intake logs
    intake_logs_r = (
        supabase.table("activity_logs")
        .select("*")
        .eq("owner_user_id", uid)
        .in_("type", ["intake", "intake_undo"])
        .gte("timestamp", since_iso)
        .lte("timestamp", until_iso)
        .execute()
    )

    # Purchase logs
    purchase_logs_r = (
        supabase.table("activity_logs")
        .select("*")
        .eq("owner_user_id", uid)
        .in_("type", ["purchase", "purchase_undo"])
        .gte("timestamp", since_iso)
        .lte("timestamp", until_iso)
        .execute()
    )

    # Monitoring
    monitoring_r = (
        supabase.table("monitoring_measurements")
        .select("*")
        .in_("tracked_medicine_id", med_ids)
        .gte("measured_at", since_iso)
        .lte("measured_at", until_iso)
        .execute()
    )

    return AdherenceSnapshotDTO(
        therapies=therapies,
        intake_logs=[ActivityLogDTO.model_validate(log) for log in intake_logs_r.data],
        medicines=[TrackedMedicineDTO.model_validate(m) for m in meds_r.data],
        purchase_logs=[ActivityLogDTO.model_validate(log) for log in purchase_logs_r.data],
        monitoring_measurements=[MonitoringMeasurementDTO.model_validate(m) for m in monitoring_r.data],
    )
