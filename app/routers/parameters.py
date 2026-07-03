from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from supabase import Client

from app.auth.models import AuthenticatedUser
from app.dependencies import get_current_user, get_supabase
from app.schemas.parameter import (
    ParameterCreateRequest,
    ParameterDTO,
)
from app.services.parameters_service import (
    create_custom_parameter,
    list_parameters,
)

router = APIRouter(prefix="/parameters", tags=["Parameters"])


@router.get("", response_model=list[ParameterDTO])
async def list_parameters_endpoint(
    profile_id: UUID = Query(...),
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await list_parameters(supabase, user.user_id, profile_id)


@router.post(
    "", response_model=ParameterDTO, status_code=status.HTTP_201_CREATED
)
async def create_parameter_endpoint(
    data: ParameterCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await create_custom_parameter(supabase, user.user_id, data)
