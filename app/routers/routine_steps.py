from uuid import UUID

from fastapi import APIRouter, Depends, status
from supabase import Client

from app.auth.models import AuthenticatedUser
from app.dependencies import get_current_user, get_supabase
from app.schemas.base import PharmaBaseModel
from app.schemas.routine_step import RoutineStepData, RoutineStepDTO
from app.services.routine_steps_service import (
    add_step,
    delete_step,
    reorder_steps,
    update_step,
)

router = APIRouter(prefix="/routines/{routine_id}/steps", tags=["Routine Steps"])


class _AddStepRequest(PharmaBaseModel):
    data: RoutineStepData
    position: int | None = None


class _ReorderRequest(PharmaBaseModel):
    ordering: list[dict]


@router.post(
    "", response_model=RoutineStepDTO, status_code=status.HTTP_201_CREATED
)
async def add_step_endpoint(
    routine_id: UUID,
    body: _AddStepRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await add_step(
        supabase, user.user_id, routine_id, body.data, body.position
    )


@router.put("/{step_id}", response_model=RoutineStepDTO)
async def update_step_endpoint(
    routine_id: UUID,
    step_id: UUID,
    data: RoutineStepData,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await update_step(
        supabase, user.user_id, routine_id, step_id, data
    )


@router.delete("/{step_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_step_endpoint(
    routine_id: UUID,
    step_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    await delete_step(supabase, user.user_id, routine_id, step_id)


@router.patch("/reorder", response_model=list[RoutineStepDTO])
async def reorder_steps_endpoint(
    routine_id: UUID,
    body: _ReorderRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await reorder_steps(
        supabase, user.user_id, routine_id, body.ordering
    )
