from fastapi import APIRouter, Depends
from supabase import Client

from app.auth.models import AuthenticatedUser
from app.dependencies import get_current_user, get_supabase
from app.schemas.settings import UserSettingsDTO, UserSettingsUpdateRequest
from app.services.settings_service import get_or_create_settings, update_settings

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get("", response_model=UserSettingsDTO)
async def get_settings_endpoint(
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await get_or_create_settings(supabase, user.user_id)


@router.put("", response_model=UserSettingsDTO)
async def update_settings_endpoint(
    data: UserSettingsUpdateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await update_settings(supabase, user.user_id, data)
