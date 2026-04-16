from uuid import UUID

from fastapi import APIRouter, Depends, status
from supabase import Client

from app.auth.models import AuthenticatedUser
from app.dependencies import get_current_user, get_supabase
from app.schemas.prescription_request import (
    PrescriptionRequestCreateRequest,
    PrescriptionRequestDTO,
    PrescriptionRequestUpdateRequest,
)
from app.services.prescription_requests_service import (
    create_prescription_request,
    get_prescription_request,
    list_prescription_requests,
    update_prescription_request,
)

router = APIRouter(
    prefix="/medications/{medication_id}/prescription_requests",
    tags=["PrescriptionRequests"],
)


@router.get("", response_model=list[PrescriptionRequestDTO])
async def list_prescription_requests_endpoint(
    medication_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await list_prescription_requests(supabase, user.user_id, medication_id)


@router.post(
    "", response_model=PrescriptionRequestDTO, status_code=status.HTTP_201_CREATED
)
async def create_prescription_request_endpoint(
    medication_id: UUID,
    data: PrescriptionRequestCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await create_prescription_request(supabase, user.user_id, medication_id, data)


@router.get("/{request_id}", response_model=PrescriptionRequestDTO)
async def get_prescription_request_endpoint(
    medication_id: UUID,
    request_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await get_prescription_request(
        supabase, user.user_id, medication_id, request_id
    )


@router.patch("/{request_id}", response_model=PrescriptionRequestDTO)
async def update_prescription_request_endpoint(
    medication_id: UUID,
    request_id: UUID,
    data: PrescriptionRequestUpdateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await update_prescription_request(
        supabase, user.user_id, medication_id, request_id, data
    )
