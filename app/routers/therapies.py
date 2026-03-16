from uuid import UUID

from fastapi import APIRouter, Depends, status
from supabase import Client

from app.auth.models import AuthenticatedUser
from app.dependencies import get_current_user, get_supabase
from app.schemas.therapy import TherapyCreateRequest, TherapyUpdateRequest, TherapyWithDosesDTO
from app.services.therapies_service import create_therapy, delete_therapy, list_therapies, update_therapy

router = APIRouter(prefix="/medicines/{medicine_id}/therapies", tags=["Therapies"])


@router.get("", response_model=list[TherapyWithDosesDTO])
async def list_therapies_endpoint(
    medicine_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await list_therapies(supabase, user.user_id, medicine_id)


@router.post("", response_model=TherapyWithDosesDTO, status_code=status.HTTP_201_CREATED)
async def create_therapy_endpoint(
    medicine_id: UUID,
    data: TherapyCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await create_therapy(supabase, user.user_id, medicine_id, data)


@router.put("/{therapy_id}", response_model=TherapyWithDosesDTO)
async def update_therapy_endpoint(
    medicine_id: UUID,
    therapy_id: UUID,
    data: TherapyUpdateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await update_therapy(supabase, user.user_id, medicine_id, therapy_id, data)


@router.delete("/{therapy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_therapy_endpoint(
    medicine_id: UUID,
    therapy_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    await delete_therapy(supabase, user.user_id, medicine_id, therapy_id)
