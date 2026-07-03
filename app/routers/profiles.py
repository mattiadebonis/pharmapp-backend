from uuid import UUID

from fastapi import APIRouter, Depends, status
from supabase import Client

from app.auth.models import AuthenticatedUser
from app.dependencies import get_current_user, get_supabase
from app.schemas.profile import ProfileDTO, ProfileUpdateRequest
from app.services.profiles_service import (
    cancel_profile_connection,
    delete_profile,
    disconnect_managed_profile,
    init_own_profile,
    resend_profile_invite,
    update_profile,
)

router = APIRouter(prefix="/profiles", tags=["Profiles"])


@router.post("/init", response_model=ProfileDTO)
async def init_own_profile_endpoint(
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Idempotent: returns the user's own profile, creating it if needed.

    Called by iOS once at the end of onboarding. Replaces the implicit
    auto-create that used to live in GET /v2/bootstrap.
    """
    return await init_own_profile(supabase, user.user_id)


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


@router.put("/{profile_id}/disconnect", response_model=ProfileDTO)
async def disconnect_profile_endpoint(
    profile_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await disconnect_managed_profile(supabase, user.user_id, profile_id)


@router.post("/{profile_id}/resend-invite", response_model=ProfileDTO)
async def resend_invite_endpoint(
    profile_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await resend_profile_invite(supabase, user.user_id, profile_id)


@router.delete("/{profile_id}/cancel", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_profile_endpoint(
    profile_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    await cancel_profile_connection(supabase, user.user_id, profile_id)
