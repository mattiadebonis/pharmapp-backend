from uuid import UUID

from fastapi import APIRouter, Depends, status
from supabase import Client

from app.auth.models import AuthenticatedUser
from app.dependencies import get_current_user, get_supabase
from app.schemas.profile import ProfileCreateRequest, ProfileDTO, ProfileUpdateRequest
from app.services.profiles_service import (
    create_profile,
    delete_profile,
    get_profile,
    list_profiles,
    update_profile,
)

router = APIRouter(prefix="/profiles", tags=["Profiles"])


@router.get("", response_model=list[ProfileDTO])
async def list_profiles_endpoint(
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await list_profiles(supabase, user.user_id)


@router.post("", response_model=ProfileDTO, status_code=status.HTTP_201_CREATED)
async def create_profile_endpoint(
    data: ProfileCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await create_profile(supabase, user.user_id, data)


@router.get("/{profile_id}", response_model=ProfileDTO)
async def get_profile_endpoint(
    profile_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await get_profile(supabase, user.user_id, profile_id)


@router.put("/{profile_id}", response_model=ProfileDTO)
async def update_profile_endpoint(
    profile_id: UUID,
    data: ProfileUpdateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await update_profile(supabase, user.user_id, profile_id, data)


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile_endpoint(
    profile_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    await delete_profile(supabase, user.user_id, profile_id)
