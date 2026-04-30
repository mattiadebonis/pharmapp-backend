from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from supabase import Client

from app.auth.models import AuthenticatedUser
from app.dependencies import get_current_user, get_supabase
from app.schemas.measurement import (
    MeasurementCreateRequest,
    MeasurementDTO,
    MeasurementUpdateRequest,
)
from app.services.measurements_service import (
    create_measurement,
    delete_measurement,
    get_measurement,
    list_measurements,
    update_measurement,
)

router = APIRouter(prefix="/measurements", tags=["Measurements"])


@router.get("", response_model=list[MeasurementDTO])
async def list_measurements_endpoint(
    profile_id: UUID = Query(...),
    parameter_key: str | None = Query(default=None),
    from_dt: datetime | None = Query(default=None, alias="from"),
    to_dt: datetime | None = Query(default=None, alias="to"),
    limit: int = Query(default=500, ge=1, le=2000),
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await list_measurements(
        supabase,
        user.user_id,
        profile_id,
        parameter_key=parameter_key,
        from_dt=from_dt,
        to_dt=to_dt,
        limit=limit,
    )


@router.post(
    "", response_model=MeasurementDTO, status_code=status.HTTP_201_CREATED
)
async def create_measurement_endpoint(
    data: MeasurementCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await create_measurement(supabase, user.user_id, data)


@router.get("/{measurement_id}", response_model=MeasurementDTO)
async def get_measurement_endpoint(
    measurement_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await get_measurement(supabase, user.user_id, measurement_id)


@router.patch("/{measurement_id}", response_model=MeasurementDTO)
async def update_measurement_endpoint(
    measurement_id: UUID,
    data: MeasurementUpdateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await update_measurement(
        supabase, user.user_id, measurement_id, data
    )


@router.delete("/{measurement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_measurement_endpoint(
    measurement_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    await delete_measurement(supabase, user.user_id, measurement_id)
