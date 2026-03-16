from uuid import UUID

from supabase import Client

from app.schemas.doctor import DoctorCreateRequest, DoctorDTO, DoctorUpdateRequest
from app.services.authorization import assert_owner


async def list_doctors(supabase: Client, user_id: UUID) -> list[DoctorDTO]:
    result = supabase.table("doctors").select("*").eq("owner_user_id", str(user_id)).execute()
    return [DoctorDTO.model_validate(row) for row in result.data]


async def get_doctor(supabase: Client, user_id: UUID, doctor_id: UUID) -> DoctorDTO:
    await assert_owner(supabase, user_id, "doctors", doctor_id)
    result = supabase.table("doctors").select("*").eq("id", str(doctor_id)).single().execute()
    return DoctorDTO.model_validate(result.data)


async def create_doctor(supabase: Client, user_id: UUID, data: DoctorCreateRequest) -> DoctorDTO:
    insert_data = data.model_dump()
    insert_data["owner_user_id"] = str(user_id)
    result = supabase.table("doctors").insert(insert_data).execute()
    return DoctorDTO.model_validate(result.data[0])


async def update_doctor(supabase: Client, user_id: UUID, doctor_id: UUID, data: DoctorUpdateRequest) -> DoctorDTO:
    await assert_owner(supabase, user_id, "doctors", doctor_id)
    update_data = data.model_dump(exclude_unset=True)
    result = supabase.table("doctors").update(update_data).eq("id", str(doctor_id)).execute()
    return DoctorDTO.model_validate(result.data[0])


async def delete_doctor(supabase: Client, user_id: UUID, doctor_id: UUID) -> None:
    await assert_owner(supabase, user_id, "doctors", doctor_id)
    supabase.table("doctors").delete().eq("id", str(doctor_id)).execute()
