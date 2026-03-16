from uuid import UUID

from fastapi import APIRouter, Depends, status
from supabase import Client

from app.auth.models import AuthenticatedUser
from app.dependencies import get_current_user, get_supabase
from app.schemas.custom_filter import CustomFilterCreateRequest, CustomFilterDTO, CustomFilterUpdateRequest
from app.services.custom_filters_service import create_filter, delete_filter, list_filters, update_filter

router = APIRouter(prefix="/custom-filters", tags=["Custom Filters"])


@router.get("", response_model=list[CustomFilterDTO])
async def list_filters_endpoint(
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await list_filters(supabase, user.user_id)


@router.post("", response_model=CustomFilterDTO, status_code=status.HTTP_201_CREATED)
async def create_filter_endpoint(
    data: CustomFilterCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await create_filter(supabase, user.user_id, data)


@router.put("/{filter_id}", response_model=CustomFilterDTO)
async def update_filter_endpoint(
    filter_id: UUID,
    data: CustomFilterUpdateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await update_filter(supabase, user.user_id, filter_id, data)


@router.delete("/{filter_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_filter_endpoint(
    filter_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    await delete_filter(supabase, user.user_id, filter_id)
