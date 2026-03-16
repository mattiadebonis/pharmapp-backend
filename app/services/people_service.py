from uuid import UUID

from supabase import Client

from app.schemas.person import PersonCreateRequest, PersonDTO, PersonUpdateRequest
from app.services.authorization import assert_owner


async def list_people(supabase: Client, user_id: UUID) -> list[PersonDTO]:
    result = supabase.table("people").select("*").eq("owner_user_id", str(user_id)).execute()
    return [PersonDTO.model_validate(row) for row in result.data]


async def get_person(supabase: Client, user_id: UUID, person_id: UUID) -> PersonDTO:
    await assert_owner(supabase, user_id, "people", person_id)
    result = supabase.table("people").select("*").eq("id", str(person_id)).single().execute()
    return PersonDTO.model_validate(result.data)


async def create_person(supabase: Client, user_id: UUID, data: PersonCreateRequest) -> PersonDTO:
    insert_data = data.model_dump()
    insert_data["owner_user_id"] = str(user_id)
    result = supabase.table("people").insert(insert_data).execute()
    return PersonDTO.model_validate(result.data[0])


async def update_person(supabase: Client, user_id: UUID, person_id: UUID, data: PersonUpdateRequest) -> PersonDTO:
    await assert_owner(supabase, user_id, "people", person_id)
    update_data = data.model_dump(exclude_unset=True)
    result = supabase.table("people").update(update_data).eq("id", str(person_id)).execute()
    return PersonDTO.model_validate(result.data[0])


async def delete_person(supabase: Client, user_id: UUID, person_id: UUID) -> None:
    await assert_owner(supabase, user_id, "people", person_id)
    supabase.table("people").delete().eq("id", str(person_id)).execute()
