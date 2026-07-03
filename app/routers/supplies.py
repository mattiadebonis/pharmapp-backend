from uuid import UUID

from fastapi import APIRouter, Depends
from supabase import Client

from app.auth.models import AuthenticatedUser
from app.dependencies import get_current_user, get_supabase
from app.schemas.supply import SupplyDTO, SupplyUpdateRequest
from app.services.supplies_service import upsert_supply

router = APIRouter(prefix="/medications/{medication_id}/supply", tags=["Supplies"])


@router.put("", response_model=SupplyDTO)
async def upsert_supply_endpoint(
    medication_id: UUID,
    data: SupplyUpdateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await upsert_supply(supabase, user.user_id, medication_id, data)
