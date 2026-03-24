from fastapi import APIRouter, Depends
from supabase import Client

from app.auth.models import AuthenticatedUser
from app.dependencies import get_current_user, get_supabase
from app.schemas.bootstrap import BootstrapResponse
from app.services.bootstrap_service import get_bootstrap_data

router = APIRouter(prefix="/bootstrap", tags=["Bootstrap"])


@router.get("", response_model=BootstrapResponse)
async def bootstrap_endpoint(
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Fetch all user data in a single call for app startup / offline sync."""
    return await get_bootstrap_data(supabase, user.user_id)
