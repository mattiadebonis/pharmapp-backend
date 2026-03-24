from uuid import UUID

from fastapi import APIRouter, Depends, status
from supabase import Client

from app.auth.models import AuthenticatedUser
from app.dependencies import get_current_user, get_supabase
from app.schemas.medication import (
    MedicationCreateRequest,
    MedicationDTO,
    MedicationUpdateRequest,
    MedicationWithDetailsDTO,
)
from app.services.medications_service import (
    create_medication,
    delete_medication,
    get_medication,
    get_medication_with_details,
    list_medications,
    update_medication,
)

router = APIRouter(prefix="/medications", tags=["Medications"])


@router.get("", response_model=list[MedicationDTO])
async def list_medications_endpoint(
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await list_medications(supabase, user.user_id)


@router.post("", response_model=MedicationDTO, status_code=status.HTTP_201_CREATED)
async def create_medication_endpoint(
    data: MedicationCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await create_medication(supabase, user.user_id, data)


@router.get("/{medication_id}", response_model=MedicationWithDetailsDTO)
async def get_medication_endpoint(
    medication_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await get_medication_with_details(supabase, user.user_id, medication_id)


@router.put("/{medication_id}", response_model=MedicationDTO)
async def update_medication_endpoint(
    medication_id: UUID,
    data: MedicationUpdateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await update_medication(supabase, user.user_id, medication_id, data)


@router.delete("/{medication_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_medication_endpoint(
    medication_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    await delete_medication(supabase, user.user_id, medication_id)
