from uuid import UUID

from fastapi import APIRouter, Depends, status
from supabase import Client

from app.auth.models import AuthenticatedUser
from app.dependencies import get_current_user, get_supabase
from app.schemas.dosing_schedule import (
    DosingScheduleCreateRequest,
    DosingScheduleDTO,
    DosingScheduleUpdateRequest,
)
from app.services.dosing_schedules_service import (
    create_dosing_schedule,
    delete_dosing_schedule,
    get_dosing_schedule,
    list_dosing_schedules,
    update_dosing_schedule,
)

router = APIRouter(prefix="/medications/{medication_id}/schedules", tags=["Dosing Schedules"])


@router.get("", response_model=list[DosingScheduleDTO])
async def list_schedules_endpoint(
    medication_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await list_dosing_schedules(supabase, user.user_id, medication_id)


@router.post("", response_model=DosingScheduleDTO, status_code=status.HTTP_201_CREATED)
async def create_schedule_endpoint(
    medication_id: UUID,
    data: DosingScheduleCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await create_dosing_schedule(supabase, user.user_id, medication_id, data)


@router.get("/{schedule_id}", response_model=DosingScheduleDTO)
async def get_schedule_endpoint(
    medication_id: UUID,
    schedule_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await get_dosing_schedule(supabase, user.user_id, medication_id, schedule_id)


@router.put("/{schedule_id}", response_model=DosingScheduleDTO)
async def update_schedule_endpoint(
    medication_id: UUID,
    schedule_id: UUID,
    data: DosingScheduleUpdateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await update_dosing_schedule(supabase, user.user_id, medication_id, schedule_id, data)


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule_endpoint(
    medication_id: UUID,
    schedule_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    await delete_dosing_schedule(supabase, user.user_id, medication_id, schedule_id)
