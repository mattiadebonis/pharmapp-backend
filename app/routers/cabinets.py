from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from supabase import Client

from app.auth.models import AuthenticatedUser
from app.dependencies import get_current_user, get_supabase
from app.schemas.cabinet import (
    CabinetCreateRequest,
    CabinetDTO,
    CabinetMembershipCreateRequest,
    CabinetMembershipDTO,
    CabinetMembershipUpdateRequest,
    CabinetUpdateRequest,
    CabinetWithMembershipsDTO,
)
from app.services.cabinets_service import (
    create_cabinet,
    create_membership,
    delete_cabinet,
    delete_membership,
    list_cabinets,
    update_cabinet,
    update_membership,
)

router = APIRouter(prefix="/cabinets", tags=["Cabinets"])


@router.get("", response_model=list[CabinetWithMembershipsDTO])
async def list_cabinets_endpoint(
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await list_cabinets(supabase, user.user_id)


@router.post("", response_model=CabinetDTO, status_code=status.HTTP_201_CREATED)
async def create_cabinet_endpoint(
    data: CabinetCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await create_cabinet(supabase, user.user_id, data)


@router.put("/{cabinet_id}", response_model=CabinetDTO)
async def update_cabinet_endpoint(
    cabinet_id: UUID,
    data: CabinetUpdateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await update_cabinet(supabase, user.user_id, cabinet_id, data)


@router.delete("/{cabinet_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cabinet_endpoint(
    cabinet_id: UUID,
    move_to: UUID | None = Query(None),
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    await delete_cabinet(supabase, user.user_id, cabinet_id, move_to)


@router.post("/{cabinet_id}/memberships", response_model=CabinetMembershipDTO, status_code=status.HTTP_201_CREATED)
async def create_membership_endpoint(
    cabinet_id: UUID,
    data: CabinetMembershipCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await create_membership(supabase, user.user_id, cabinet_id, data)


@router.put("/{cabinet_id}/memberships/{membership_id}", response_model=CabinetMembershipDTO)
async def update_membership_endpoint(
    cabinet_id: UUID,
    membership_id: UUID,
    data: CabinetMembershipUpdateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await update_membership(supabase, user.user_id, cabinet_id, membership_id, data)


@router.delete("/{cabinet_id}/memberships/{membership_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_membership_endpoint(
    cabinet_id: UUID,
    membership_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    await delete_membership(supabase, user.user_id, cabinet_id, membership_id)
