from uuid import UUID

from fastapi import APIRouter, Depends
from supabase import Client

from app.auth.models import AuthenticatedUser
from app.dependencies import get_current_user, get_supabase
from app.schemas.stock import StockDTO, StockIncrementRequest, StockSetRequest
from app.services.stocks_service import get_stocks, increment_stock, set_stock

router = APIRouter(prefix="/stocks", tags=["Stocks"])


@router.get("", response_model=list[StockDTO])
async def list_stocks_endpoint(
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await get_stocks(supabase, user.user_id)


@router.put("/{tracked_package_id}", response_model=StockDTO)
async def set_stock_endpoint(
    tracked_package_id: UUID,
    data: StockSetRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await set_stock(supabase, user.user_id, tracked_package_id, data)


@router.post("/{tracked_package_id}/increment", response_model=StockDTO)
async def increment_stock_endpoint(
    tracked_package_id: UUID,
    data: StockIncrementRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await increment_stock(supabase, user.user_id, tracked_package_id, data)
