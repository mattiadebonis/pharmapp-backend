from uuid import UUID

from fastapi import APIRouter, Depends, status
from supabase import Client

from app.auth.models import AuthenticatedUser
from app.dependencies import get_current_user, get_supabase
from app.schemas.medication import (
    MedicationCreateRequest,
    MedicationDTO,
    MedicationUpdateRequest,
)
from app.services.medications_service import (
    create_medication,
    delete_medication,
    update_medication,
)

router = APIRouter(prefix="/medications", tags=["Medications"])


@router.post("", response_model=MedicationDTO, status_code=status.HTTP_201_CREATED)
async def create_medication_endpoint(
    data: MedicationCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await create_medication(supabase, user.user_id, data)


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
