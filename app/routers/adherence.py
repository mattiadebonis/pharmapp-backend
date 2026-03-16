from datetime import datetime

from fastapi import APIRouter, Depends, Query
from supabase import Client

from app.auth.models import AuthenticatedUser
from app.dependencies import get_current_user, get_supabase
from app.schemas.adherence import AdherenceSnapshotDTO
from app.services.adherence_service import get_adherence

router = APIRouter(prefix="/adherence", tags=["Adherence"])


@router.get("", response_model=AdherenceSnapshotDTO)
async def adherence_endpoint(
    since: datetime = Query(...),
    until: datetime = Query(...),
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await get_adherence(supabase, user.user_id, since, until)
