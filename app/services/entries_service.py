from uuid import UUID

from supabase import Client

from app.schemas.entry import MedicineEntryCreateRequest, MedicineEntryDTO, MedicineEntryUpdateRequest
from app.services.authorization import assert_can_access_tracked_medicine


async def list_entries(supabase: Client, user_id: UUID, medicine_id: UUID) -> list[MedicineEntryDTO]:
    await assert_can_access_tracked_medicine(supabase, user_id, medicine_id)
    result = supabase.table("medicine_entries").select("*").eq("tracked_medicine_id", str(medicine_id)).execute()
    return [MedicineEntryDTO.model_validate(row) for row in result.data]


async def create_entry(
    supabase: Client, user_id: UUID, medicine_id: UUID, data: MedicineEntryCreateRequest
) -> MedicineEntryDTO:
    await assert_can_access_tracked_medicine(supabase, user_id, medicine_id)
    insert_data = data.model_dump()
    insert_data["tracked_medicine_id"] = str(medicine_id)
    if insert_data.get("tracked_package_id"):
        insert_data["tracked_package_id"] = str(insert_data["tracked_package_id"])
    if insert_data.get("cabinet_id"):
        insert_data["cabinet_id"] = str(insert_data["cabinet_id"])
    result = supabase.table("medicine_entries").insert(insert_data).execute()
    return MedicineEntryDTO.model_validate(result.data[0])


async def update_entry(
    supabase: Client, user_id: UUID, medicine_id: UUID, entry_id: UUID, data: MedicineEntryUpdateRequest
) -> MedicineEntryDTO:
    await assert_can_access_tracked_medicine(supabase, user_id, medicine_id)
    update_data = data.model_dump(exclude_unset=True)
    if "cabinet_id" in update_data and update_data["cabinet_id"]:
        update_data["cabinet_id"] = str(update_data["cabinet_id"])
    result = supabase.table("medicine_entries").update(update_data).eq("id", str(entry_id)).execute()
    return MedicineEntryDTO.model_validate(result.data[0])


async def delete_entry(supabase: Client, user_id: UUID, medicine_id: UUID, entry_id: UUID) -> None:
    await assert_can_access_tracked_medicine(supabase, user_id, medicine_id)
    supabase.table("medicine_entries").delete().eq("id", str(entry_id)).execute()
