from fastapi import APIRouter, Depends
from supabase import Client

from app.auth.models import AuthenticatedUser
from app.dependencies import get_current_user, get_supabase
from app.schemas.bootstrap import BootstrapResponse
from app.services.bootstrap_service import fetch_bootstrap

router = APIRouter(tags=["Bootstrap"])


@router.get("/bootstrap", response_model=BootstrapResponse)
async def bootstrap(
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await fetch_bootstrap(supabase, user.user_id)
