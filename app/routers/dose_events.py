from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from supabase import Client

from app.auth.models import AuthenticatedUser
from app.dependencies import get_current_user, get_supabase
from app.schemas.dose_event import DoseEventCreateRequest, DoseEventDTO, DoseEventUpdateRequest
from app.services.dose_events_service import (
    create_dose_event,
    delete_dose_event,
    get_dose_event,
    list_dose_events,
    update_dose_event,
)

router = APIRouter(prefix="/dose-events", tags=["Dose Events"])


@router.get("", response_model=list[DoseEventDTO])
async def list_dose_events_endpoint(
    medication_id: UUID | None = Query(None),
    profile_id: UUID | None = Query(None),
    since: datetime | None = Query(None),
    until: datetime | None = Query(None),
    event_status: str | None = Query(None, alias="status"),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await list_dose_events(
        supabase,
        user.user_id,
        medication_id=medication_id,
        profile_id=profile_id,
        since=since,
        until=until,
        event_status=event_status,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=DoseEventDTO, status_code=status.HTTP_201_CREATED)
async def create_dose_event_endpoint(
    data: DoseEventCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await create_dose_event(supabase, user.user_id, data)


@router.get("/{event_id}", response_model=DoseEventDTO)
async def get_dose_event_endpoint(
    event_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await get_dose_event(supabase, user.user_id, event_id)


@router.put("/{event_id}", response_model=DoseEventDTO)
async def update_dose_event_endpoint(
    event_id: UUID,
    data: DoseEventUpdateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await update_dose_event(supabase, user.user_id, event_id, data)


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dose_event_endpoint(
    event_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    await delete_dose_event(supabase, user.user_id, event_id)
