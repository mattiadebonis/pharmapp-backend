from uuid import UUID

from supabase import Client

from app.schemas.therapy import TherapyCreateRequest, TherapyUpdateRequest, TherapyWithDosesDTO
from app.services.authorization import assert_can_access_tracked_medicine


async def _get_therapy_with_doses(supabase: Client, therapy_id: str) -> TherapyWithDosesDTO:
    therapy_r = supabase.table("therapies").select("*").eq("id", therapy_id).single().execute()
    doses_r = supabase.table("therapy_doses").select("*").eq("therapy_id", therapy_id).order("sort_order").execute()
    return TherapyWithDosesDTO.model_validate({**therapy_r.data, "doses": doses_r.data})


async def list_therapies(supabase: Client, user_id: UUID, medicine_id: UUID) -> list[TherapyWithDosesDTO]:
    await assert_can_access_tracked_medicine(supabase, user_id, medicine_id)
    therapies_r = supabase.table("therapies").select("*").eq("tracked_medicine_id", str(medicine_id)).execute()
    if not therapies_r.data:
        return []
    therapy_ids = [t["id"] for t in therapies_r.data]
    doses_r = supabase.table("therapy_doses").select("*").in_("therapy_id", therapy_ids).order("sort_order").execute()

    doses_by_therapy: dict[str, list] = {}
    for d in doses_r.data:
        doses_by_therapy.setdefault(d["therapy_id"], []).append(d)

    return [
        TherapyWithDosesDTO.model_validate({**t, "doses": doses_by_therapy.get(t["id"], [])})
        for t in therapies_r.data
    ]


async def create_therapy(
    supabase: Client, user_id: UUID, medicine_id: UUID, data: TherapyCreateRequest
) -> TherapyWithDosesDTO:
    await assert_can_access_tracked_medicine(supabase, user_id, medicine_id)
    therapy_data = data.model_dump(exclude={"doses"})
    therapy_data["tracked_medicine_id"] = str(medicine_id)
    # Convert UUIDs to strings
    for key in ("tracked_package_id", "medicine_entry_id", "person_id", "doctor_id"):
        if therapy_data.get(key):
            therapy_data[key] = str(therapy_data[key])
    if therapy_data.get("start_date"):
        therapy_data["start_date"] = therapy_data["start_date"].isoformat()

    therapy_r = supabase.table("therapies").insert(therapy_data).execute()
    therapy_id = therapy_r.data[0]["id"]

    if data.doses:
        doses_data = [
            {
                "therapy_id": therapy_id,
                "time": dose.time,
                "amount": dose.amount,
                "sort_order": idx,
            }
            for idx, dose in enumerate(data.doses)
        ]
        supabase.table("therapy_doses").insert(doses_data).execute()

    return await _get_therapy_with_doses(supabase, therapy_id)


async def update_therapy(
    supabase: Client, user_id: UUID, medicine_id: UUID, therapy_id: UUID, data: TherapyUpdateRequest
) -> TherapyWithDosesDTO:
    await assert_can_access_tracked_medicine(supabase, user_id, medicine_id)
    tid = str(therapy_id)

    update_data = data.model_dump(exclude={"doses"}, exclude_unset=True)
    for key in ("tracked_package_id", "medicine_entry_id", "person_id", "doctor_id"):
        if key in update_data and update_data[key]:
            update_data[key] = str(update_data[key])
    if "start_date" in update_data and update_data["start_date"]:
        update_data["start_date"] = update_data["start_date"].isoformat()

    if update_data:
        supabase.table("therapies").update(update_data).eq("id", tid).execute()

    # Replace doses if provided
    if data.doses is not None:
        supabase.table("therapy_doses").delete().eq("therapy_id", tid).execute()
        if data.doses:
            doses_data = [
                {
                    "therapy_id": tid,
                    "time": dose.time,
                    "amount": dose.amount,
                    "sort_order": idx,
                }
                for idx, dose in enumerate(data.doses)
            ]
            supabase.table("therapy_doses").insert(doses_data).execute()

    return await _get_therapy_with_doses(supabase, tid)


async def delete_therapy(supabase: Client, user_id: UUID, medicine_id: UUID, therapy_id: UUID) -> None:
    await assert_can_access_tracked_medicine(supabase, user_id, medicine_id)
    supabase.table("therapies").delete().eq("id", str(therapy_id)).execute()
