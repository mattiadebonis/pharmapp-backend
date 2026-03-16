from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from supabase import Client

from app.auth.models import AuthenticatedUser
from app.dependencies import get_current_user, get_supabase
from app.schemas.monitoring import MonitoringMeasurementCreateRequest, MonitoringMeasurementDTO
from app.services.monitoring_service import create_measurement, delete_measurement, list_measurements

router = APIRouter(prefix="/monitoring", tags=["Monitoring"])


@router.get("", response_model=list[MonitoringMeasurementDTO])
async def list_measurements_endpoint(
    medicine_id: UUID | None = Query(None),
    since: datetime | None = Query(None),
    until: datetime | None = Query(None),
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await list_measurements(supabase, user.user_id, medicine_id, since, until)


@router.post("", response_model=MonitoringMeasurementDTO, status_code=status.HTTP_201_CREATED)
async def create_measurement_endpoint(
    data: MonitoringMeasurementCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await create_measurement(supabase, user.user_id, data)


@router.delete("/{measurement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_measurement_endpoint(
    measurement_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    await delete_measurement(supabase, user.user_id, measurement_id)
