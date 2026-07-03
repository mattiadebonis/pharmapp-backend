from uuid import UUID

from fastapi import APIRouter, Depends
from supabase import Client

from app.auth.models import AuthenticatedUser
from app.dependencies import get_current_user, get_supabase
from app.schemas.dosing_schedule import (
    DosingScheduleDTO,
    DosingScheduleUpdateRequest,
)
from app.services.dosing_schedules_service import update_dosing_schedule

router = APIRouter(prefix="/medications/{medication_id}/schedules", tags=["Dosing Schedules"])


@router.put("/{schedule_id}", response_model=DosingScheduleDTO)
async def update_schedule_endpoint(
    medication_id: UUID,
    schedule_id: UUID,
    data: DosingScheduleUpdateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await update_dosing_schedule(supabase, user.user_id, medication_id, schedule_id, data)
