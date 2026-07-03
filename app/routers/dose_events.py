from fastapi import APIRouter, Depends, status
from supabase import Client

from app.auth.models import AuthenticatedUser
from app.dependencies import get_current_user, get_supabase
from app.schemas.dose_event import (
    DoseEventBatchCreateRequest,
    DoseEventBatchResponse,
    DoseEventCreateRequest,
    DoseEventDTO,
)
from app.services.dose_events_service import (
    batch_upsert_dose_events,
    create_dose_event,
)

router = APIRouter(prefix="/dose-events", tags=["Dose Events"])


@router.post("", response_model=DoseEventDTO, status_code=status.HTTP_201_CREATED)
async def create_dose_event_endpoint(
    data: DoseEventCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await create_dose_event(supabase, user.user_id, data)


# 200 e non 201: è un upsert idempotente (catch-up dosi passive arretrate),
# il ri-POST dello stesso batch non crea nulla di nuovo.
@router.post("/batch", response_model=DoseEventBatchResponse, status_code=status.HTTP_200_OK)
async def batch_upsert_dose_events_endpoint(
    data: DoseEventBatchCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await batch_upsert_dose_events(supabase, user.user_id, data)
