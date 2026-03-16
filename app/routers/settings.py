from fastapi import APIRouter, Depends
from supabase import Client

from app.auth.models import AuthenticatedUser
from app.dependencies import get_current_user, get_supabase
from app.schemas.profile import ProfileDTO, ProfileUpdateRequest
from app.schemas.settings import UserSettingsDTO, UserSettingsUpdateRequest
from app.services.settings_service import get_profile, get_settings, update_profile, update_settings

router = APIRouter(tags=["Settings"])


@router.get("/settings", response_model=UserSettingsDTO)
async def get_settings_endpoint(
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await get_settings(supabase, user.user_id)


@router.put("/settings", response_model=UserSettingsDTO)
async def update_settings_endpoint(
    data: UserSettingsUpdateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await update_settings(supabase, user.user_id, data)


@router.get("/profile", response_model=ProfileDTO)
async def get_profile_endpoint(
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await get_profile(supabase, user.user_id)


@router.put("/profile", response_model=ProfileDTO)
async def update_profile_endpoint(
    data: ProfileUpdateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await update_profile(supabase, user.user_id, data)
