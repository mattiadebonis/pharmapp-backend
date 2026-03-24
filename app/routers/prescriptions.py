from uuid import UUID

from fastapi import APIRouter, Depends, status
from supabase import Client

from app.auth.models import AuthenticatedUser
from app.dependencies import get_current_user, get_supabase
from app.schemas.prescription import (
    PrescriptionCreateRequest,
    PrescriptionDTO,
    PrescriptionUpdateRequest,
)
from app.services.prescriptions_service import (
    create_prescription,
    delete_prescription,
    get_prescription,
    list_prescriptions,
    update_prescription,
)

router = APIRouter(prefix="/medications/{medication_id}/prescriptions", tags=["Prescriptions"])


@router.get("", response_model=list[PrescriptionDTO])
async def list_prescriptions_endpoint(
    medication_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await list_prescriptions(supabase, user.user_id, medication_id)


@router.post("", response_model=PrescriptionDTO, status_code=status.HTTP_201_CREATED)
async def create_prescription_endpoint(
    medication_id: UUID,
    data: PrescriptionCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await create_prescription(supabase, user.user_id, medication_id, data)


@router.get("/{prescription_id}", response_model=PrescriptionDTO)
async def get_prescription_endpoint(
    medication_id: UUID,
    prescription_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await get_prescription(supabase, user.user_id, medication_id, prescription_id)


@router.put("/{prescription_id}", response_model=PrescriptionDTO)
async def update_prescription_endpoint(
    medication_id: UUID,
    prescription_id: UUID,
    data: PrescriptionUpdateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await update_prescription(supabase, user.user_id, medication_id, prescription_id, data)


@router.delete("/{prescription_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prescription_endpoint(
    medication_id: UUID,
    prescription_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    await delete_prescription(supabase, user.user_id, medication_id, prescription_id)
