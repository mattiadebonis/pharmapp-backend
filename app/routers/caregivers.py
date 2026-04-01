from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from slowapi import Limiter
from supabase import Client

from app.auth.models import AuthenticatedUser
from app.dependencies import get_current_user, get_supabase
from app.middleware.rate_limit import limiter
from app.schemas.caregiver import (
    CaregiverAcceptRequest,
    CaregiverInviteRequest,
    CaregiverRelationDTO,
    PendingChangeCreateRequest,
    PendingChangeDTO,
)
from app.services.caregivers_service import (
    accept_invite,
    confirm_invite,
    approve_change,
    create_invite,
    create_pending_change,
    list_patient_confirmations,
    list_pending_changes,
    list_relations,
    reject_invite,
    reject_change,
    revoke_relation,
)

router = APIRouter(prefix="/caregivers", tags=["Caregivers"])


# ---------------------------------------------------------------------------
# Relations
# ---------------------------------------------------------------------------


@router.get("/relations", response_model=list[CaregiverRelationDTO])
async def list_relations_endpoint(
    role: str | None = Query(None, pattern="^(patient|caregiver)$"),
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await list_relations(supabase, user.user_id, role)


@router.post("/invite", response_model=CaregiverRelationDTO, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def create_invite_endpoint(
    request: Request,
    data: CaregiverInviteRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await create_invite(supabase, user.user_id, data.permissions)


@router.post("/accept", response_model=CaregiverRelationDTO)
@limiter.limit("5/minute")
async def accept_invite_endpoint(
    request: Request,
    data: CaregiverAcceptRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await accept_invite(supabase, user.user_id, data.invite_code)


@router.get("/confirmations", response_model=list[CaregiverRelationDTO])
async def list_confirmations_endpoint(
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await list_patient_confirmations(supabase, user.user_id)


@router.put("/relations/{relation_id}/confirm", response_model=CaregiverRelationDTO)
async def confirm_invite_endpoint(
    relation_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await confirm_invite(supabase, user.user_id, relation_id)


@router.put("/relations/{relation_id}/reject", response_model=CaregiverRelationDTO)
async def reject_invite_endpoint(
    relation_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await reject_invite(supabase, user.user_id, relation_id)


@router.put("/relations/{relation_id}/revoke", response_model=CaregiverRelationDTO)
async def revoke_relation_endpoint(
    relation_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await revoke_relation(supabase, user.user_id, relation_id)


# ---------------------------------------------------------------------------
# Pending changes
# ---------------------------------------------------------------------------


@router.get("/pending-changes", response_model=list[PendingChangeDTO])
async def list_pending_changes_endpoint(
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await list_pending_changes(supabase, user.user_id)


@router.post(
    "/relations/{relation_id}/changes",
    response_model=PendingChangeDTO,
    status_code=status.HTTP_201_CREATED,
)
async def create_pending_change_endpoint(
    relation_id: UUID,
    data: PendingChangeCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await create_pending_change(supabase, user.user_id, relation_id, data)


@router.put("/pending-changes/{change_id}/approve", response_model=PendingChangeDTO)
async def approve_change_endpoint(
    change_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await approve_change(supabase, user.user_id, change_id)


@router.put("/pending-changes/{change_id}/reject", response_model=PendingChangeDTO)
async def reject_change_endpoint(
    change_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await reject_change(supabase, user.user_id, change_id)
