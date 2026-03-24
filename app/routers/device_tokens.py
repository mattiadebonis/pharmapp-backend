from fastapi import APIRouter, Depends, status
from supabase import Client

from app.auth.models import AuthenticatedUser
from app.dependencies import get_current_user, get_supabase
from app.schemas.device_token import DeviceTokenCreateRequest, DeviceTokenDTO
from app.services.device_tokens_service import list_tokens, register_token, remove_token

router = APIRouter(prefix="/device-tokens", tags=["Device Tokens"])


@router.get("", response_model=list[DeviceTokenDTO])
async def list_tokens_endpoint(
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await list_tokens(supabase, user.user_id)


@router.post("", response_model=DeviceTokenDTO, status_code=status.HTTP_201_CREATED)
async def register_token_endpoint(
    data: DeviceTokenCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await register_token(supabase, user.user_id, data.token, data.platform)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def remove_token_endpoint(
    data: DeviceTokenCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    await remove_token(supabase, user.user_id, data.token)
