from datetime import datetime
from uuid import UUID

from supabase import Client

from app.schemas.monitoring import MonitoringMeasurementCreateRequest, MonitoringMeasurementDTO
from app.services.authorization import assert_can_access_tracked_medicine


async def list_measurements(
    supabase: Client,
    user_id: UUID,
    medicine_id: UUID | None,
    since: datetime | None,
    until: datetime | None,
) -> list[MonitoringMeasurementDTO]:
    """List monitoring measurements with optional filters."""
    if medicine_id:
        await assert_can_access_tracked_medicine(supabase, user_id, medicine_id)
        query = supabase.table("monitoring_measurements").select("*").eq("tracked_medicine_id", str(medicine_id))
    else:
        meds_r = supabase.table("tracked_medicines").select("id").eq("owner_user_id", str(user_id)).execute()
        if not meds_r.data:
            return []
        med_ids = [m["id"] for m in meds_r.data]
        query = supabase.table("monitoring_measurements").select("*").in_("tracked_medicine_id", med_ids)
    if since:
        query = query.gte("measured_at", since.isoformat())
    if until:
        query = query.lte("measured_at", until.isoformat())
    result = query.order("measured_at", desc=True).execute()
    return [MonitoringMeasurementDTO.model_validate(row) for row in result.data]


async def create_measurement(
    supabase: Client, user_id: UUID, data: MonitoringMeasurementCreateRequest,
) -> MonitoringMeasurementDTO:
    if data.tracked_medicine_id:
        await assert_can_access_tracked_medicine(supabase, user_id, data.tracked_medicine_id)
    insert_data = data.model_dump()
    if insert_data.get("tracked_medicine_id"):
        insert_data["tracked_medicine_id"] = str(insert_data["tracked_medicine_id"])
    if insert_data.get("therapy_id"):
        insert_data["therapy_id"] = str(insert_data["therapy_id"])
    if insert_data.get("measured_at"):
        insert_data["measured_at"] = insert_data["measured_at"].isoformat()
    if insert_data.get("scheduled_at"):
        insert_data["scheduled_at"] = insert_data["scheduled_at"].isoformat()
    result = supabase.table("monitoring_measurements").insert(insert_data).execute()
    return MonitoringMeasurementDTO.model_validate(result.data[0])


async def delete_measurement(supabase: Client, user_id: UUID, measurement_id: UUID) -> None:
    event = (
        supabase.table("monitoring_measurements")
        .select("tracked_medicine_id")
        .eq("id", str(measurement_id))
        .single()
        .execute()
    )
    if event.data.get("tracked_medicine_id"):
        await assert_can_access_tracked_medicine(supabase, user_id, UUID(event.data["tracked_medicine_id"]))
    supabase.table("monitoring_measurements").delete().eq("id", str(measurement_id)).execute()
