from datetime import datetime
from uuid import UUID

from supabase import Client

from app.schemas.dose_event import DoseEventCreateRequest, DoseEventDTO, DoseEventUpdateRequest
from app.services.authorization import assert_can_access_tracked_medicine


async def list_dose_events(
    supabase: Client,
    user_id: UUID,
    therapy_id: UUID | None,
    since: datetime | None,
    until: datetime | None,
) -> list[DoseEventDTO]:
    """List dose events with optional filters."""
    # Get all medicine IDs the user owns
    meds_r = supabase.table("tracked_medicines").select("id").eq("owner_user_id", str(user_id)).execute()
    if not meds_r.data:
        return []
    med_ids = [m["id"] for m in meds_r.data]
    query = supabase.table("dose_events").select("*").in_("tracked_medicine_id", med_ids)
    if therapy_id:
        query = query.eq("therapy_id", str(therapy_id))
    if since:
        query = query.gte("due_at", since.isoformat())
    if until:
        query = query.lte("due_at", until.isoformat())
    result = query.order("due_at", desc=True).execute()
    return [DoseEventDTO.model_validate(row) for row in result.data]


async def create_dose_event(supabase: Client, user_id: UUID, data: DoseEventCreateRequest) -> DoseEventDTO:
    await assert_can_access_tracked_medicine(supabase, user_id, data.tracked_medicine_id)
    insert_data = data.model_dump()
    insert_data["tracked_medicine_id"] = str(data.tracked_medicine_id)
    insert_data["therapy_id"] = str(data.therapy_id)
    insert_data["actor_user_id"] = str(user_id)
    if insert_data.get("due_at"):
        insert_data["due_at"] = insert_data["due_at"].isoformat()
    result = supabase.table("dose_events").insert(insert_data).execute()
    return DoseEventDTO.model_validate(result.data[0])


async def update_dose_event(
    supabase: Client, user_id: UUID, event_id: UUID, data: DoseEventUpdateRequest
) -> DoseEventDTO:
    # Get the event to check access
    event = supabase.table("dose_events").select("tracked_medicine_id").eq("id", str(event_id)).single().execute()
    await assert_can_access_tracked_medicine(supabase, user_id, UUID(event.data["tracked_medicine_id"]))
    update_data = data.model_dump(exclude_unset=True)
    update_data["actor_user_id"] = str(user_id)
    result = supabase.table("dose_events").update(update_data).eq("id", str(event_id)).execute()
    return DoseEventDTO.model_validate(result.data[0])
