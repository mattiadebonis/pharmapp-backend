from fastapi import APIRouter, Depends, status
from supabase import Client

from app.auth.models import AuthenticatedUser
from app.dependencies import get_current_user, get_supabase
from app.schemas.measurement import (
    MeasurementCreateRequest,
    MeasurementDTO,
)
from app.services.measurements_service import create_measurement

router = APIRouter(prefix="/measurements", tags=["Measurements"])


@router.post(
    "", response_model=MeasurementDTO, status_code=status.HTTP_201_CREATED
)
async def create_measurement_endpoint(
    data: MeasurementCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await create_measurement(supabase, user.user_id, data)
