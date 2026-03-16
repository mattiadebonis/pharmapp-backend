from uuid import UUID

from supabase import Client

from app.schemas.profile import ProfileDTO, ProfileUpdateRequest
from app.schemas.settings import UserSettingsDTO, UserSettingsUpdateRequest


async def get_settings(supabase: Client, user_id: UUID) -> UserSettingsDTO:
    result = supabase.table("user_settings").select("*").eq("user_id", str(user_id)).single().execute()
    return UserSettingsDTO.model_validate(result.data)


async def update_settings(supabase: Client, user_id: UUID, data: UserSettingsUpdateRequest) -> UserSettingsDTO:
    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        return await get_settings(supabase, user_id)
    result = supabase.table("user_settings").update(update_data).eq("user_id", str(user_id)).execute()
    return UserSettingsDTO.model_validate(result.data[0])


async def get_profile(supabase: Client, user_id: UUID) -> ProfileDTO:
    result = supabase.table("profiles").select("*").eq("id", str(user_id)).single().execute()
    return ProfileDTO.model_validate(result.data)


async def update_profile(supabase: Client, user_id: UUID, data: ProfileUpdateRequest) -> ProfileDTO:
    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        return await get_profile(supabase, user_id)
    result = supabase.table("profiles").update(update_data).eq("id", str(user_id)).execute()
    return ProfileDTO.model_validate(result.data[0])
