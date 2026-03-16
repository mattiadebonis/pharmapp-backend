from uuid import UUID

from supabase import Client

from app.schemas.custom_filter import CustomFilterCreateRequest, CustomFilterDTO, CustomFilterUpdateRequest
from app.services.authorization import assert_owner


async def list_filters(supabase: Client, user_id: UUID) -> list[CustomFilterDTO]:
    result = (
        supabase.table("custom_filters")
        .select("*")
        .eq("owner_user_id", str(user_id))
        .is_("deleted_at", "null")
        .order("position")
        .execute()
    )
    return [CustomFilterDTO.model_validate(row) for row in result.data]


async def create_filter(supabase: Client, user_id: UUID, data: CustomFilterCreateRequest) -> CustomFilterDTO:
    insert_data = data.model_dump()
    insert_data["owner_user_id"] = str(user_id)
    result = supabase.table("custom_filters").insert(insert_data).execute()
    return CustomFilterDTO.model_validate(result.data[0])


async def update_filter(
    supabase: Client, user_id: UUID, filter_id: UUID, data: CustomFilterUpdateRequest,
) -> CustomFilterDTO:
    await assert_owner(supabase, user_id, "custom_filters", filter_id)
    update_data = data.model_dump(exclude_unset=True)
    result = supabase.table("custom_filters").update(update_data).eq("id", str(filter_id)).execute()
    return CustomFilterDTO.model_validate(result.data[0])


async def delete_filter(supabase: Client, user_id: UUID, filter_id: UUID) -> None:
    await assert_owner(supabase, user_id, "custom_filters", filter_id)
    # Soft delete
    supabase.table("custom_filters").update({"deleted_at": "now()"}).eq("id", str(filter_id)).execute()
