from uuid import UUID

from fastapi import APIRouter, Depends, status
from supabase import Client

from app.auth.models import AuthenticatedUser
from app.dependencies import get_current_user, get_supabase
from app.schemas.routine import (
    RoutineCreateRequest,
    RoutineDTO,
    RoutineUpdateRequest,
)
from app.services.routines_service import (
    create_routine,
    delete_routine,
    get_routine,
    list_routines,
    update_routine,
)

router = APIRouter(prefix="/routines", tags=["Routines"])


@router.get("", response_model=list[RoutineDTO])
async def list_routines_endpoint(
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await list_routines(supabase, user.user_id)


@router.post("", response_model=RoutineDTO, status_code=status.HTTP_201_CREATED)
async def create_routine_endpoint(
    data: RoutineCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await create_routine(supabase, user.user_id, data)


@router.get("/{routine_id}", response_model=RoutineDTO)
async def get_routine_endpoint(
    routine_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await get_routine(supabase, user.user_id, routine_id)


@router.put("/{routine_id}", response_model=RoutineDTO)
async def update_routine_endpoint(
    routine_id: UUID,
    data: RoutineUpdateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await update_routine(supabase, user.user_id, routine_id, data)


@router.delete("/{routine_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_routine_endpoint(
    routine_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    await delete_routine(supabase, user.user_id, routine_id)
