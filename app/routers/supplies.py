from uuid import UUID

from fastapi import APIRouter, Depends, status
from supabase import Client

from app.auth.models import AuthenticatedUser
from app.dependencies import get_current_user, get_supabase
from app.schemas.supply import SupplyCreateRequest, SupplyDTO
from app.services.supplies_service import delete_supply, get_supply, upsert_supply

router = APIRouter(prefix="/medications/{medication_id}/supply", tags=["Supplies"])


@router.get("", response_model=SupplyDTO | None)
async def get_supply_endpoint(
    medication_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await get_supply(supabase, user.user_id, medication_id)


@router.put("", response_model=SupplyDTO)
async def upsert_supply_endpoint(
    medication_id: UUID,
    data: SupplyCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await upsert_supply(supabase, user.user_id, medication_id, data)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_supply_endpoint(
    medication_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    await delete_supply(supabase, user.user_id, medication_id)
