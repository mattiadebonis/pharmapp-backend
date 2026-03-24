from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from supabase import Client

from app.auth.models import AuthenticatedUser
from app.dependencies import get_current_user, get_supabase
from app.schemas.activity_log import ActivityLogCreateRequest, ActivityLogDTO
from app.services.activity_logs_service import create_log, list_logs

router = APIRouter(prefix="/activity-logs", tags=["Activity Logs"])


@router.get("", response_model=list[ActivityLogDTO])
async def list_logs_endpoint(
    medication_id: UUID | None = Query(None),
    profile_id: UUID | None = Query(None),
    action_type: str | None = Query(None),
    since: datetime | None = Query(None),
    until: datetime | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    logs, _ = await list_logs(
        supabase,
        user.user_id,
        medication_id=medication_id,
        profile_id=profile_id,
        action_type=action_type,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
    )
    return logs


@router.post("", response_model=ActivityLogDTO, status_code=status.HTTP_201_CREATED)
async def create_log_endpoint(
    data: ActivityLogCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await create_log(supabase, user.user_id, data)
