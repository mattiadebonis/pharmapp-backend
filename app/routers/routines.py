from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from supabase import Client

from app.auth.models import AuthenticatedUser
from app.dependencies import get_current_user, get_supabase
from app.schemas.base import PharmaBaseModel
from app.schemas.routine import (
    RoutineCreateRequest,
    RoutineUpdateRequest,
    RoutineWithStepsDTO,
)
from app.services.routines_service import (
    create_routine_with_steps,
    delete_routine,
    duplicate_routine,
    get_routine_with_steps,
    list_routines,
    update_routine,
)

router = APIRouter(prefix="/routines", tags=["Routines"])


class _DuplicateRequest(PharmaBaseModel):
    name: str


@router.get("", response_model=list[RoutineWithStepsDTO])
async def list_routines_endpoint(
    profile_id: UUID | None = Query(default=None),
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await list_routines(supabase, user.user_id, profile_id)


@router.post(
    "", response_model=RoutineWithStepsDTO, status_code=status.HTTP_201_CREATED
)
async def create_routine_endpoint(
    data: RoutineCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await create_routine_with_steps(supabase, user.user_id, data)


@router.get("/{routine_id}", response_model=RoutineWithStepsDTO)
async def get_routine_endpoint(
    routine_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await get_routine_with_steps(supabase, user.user_id, routine_id)


@router.put("/{routine_id}", response_model=RoutineWithStepsDTO)
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
    hard: bool = Query(default=False),
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    await delete_routine(supabase, user.user_id, routine_id, hard=hard)


@router.post(
    "/{routine_id}/duplicate",
    response_model=RoutineWithStepsDTO,
    status_code=status.HTTP_201_CREATED,
)
async def duplicate_routine_endpoint(
    routine_id: UUID,
    data: _DuplicateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await duplicate_routine(supabase, user.user_id, routine_id, data.name)
