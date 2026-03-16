from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from supabase import Client

from app.auth.models import AuthenticatedUser
from app.dependencies import get_current_user, get_supabase
from app.schemas.base import PaginatedResponse
from app.schemas.log import ActivityLogDTO
from app.services.logs_service import list_logs

router = APIRouter(prefix="/logs", tags=["Activity Logs"])


@router.get("", response_model=PaginatedResponse[ActivityLogDTO])
async def list_logs_endpoint(
    medicine_id: UUID | None = Query(None),
    since: datetime | None = Query(None),
    until: datetime | None = Query(None),
    type: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    data, total = await list_logs(supabase, user.user_id, medicine_id, since, until, type, limit, offset)
    return PaginatedResponse(data=data, total=total, limit=limit, offset=offset)
