from fastapi import APIRouter, Depends
from supabase import Client

from app.auth.models import AuthenticatedUser
from app.dependencies import get_current_user, get_supabase
from app.schemas.operation import OperationRequest, OperationResultDTO, UndoOperationRequest
from app.services.operations_service import (
    record_intake,
    record_prescription_received,
    record_prescription_request,
    record_purchase,
    undo_operation,
)

router = APIRouter(prefix="/operations", tags=["Operations"])


@router.post("/intake", response_model=OperationResultDTO)
async def intake_endpoint(
    data: OperationRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await record_intake(supabase, user.user_id, data)


@router.post("/purchase", response_model=OperationResultDTO)
async def purchase_endpoint(
    data: OperationRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await record_purchase(supabase, user.user_id, data)


@router.post("/prescription-request", response_model=OperationResultDTO)
async def prescription_request_endpoint(
    data: OperationRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await record_prescription_request(supabase, user.user_id, data)


@router.post("/prescription-received", response_model=OperationResultDTO)
async def prescription_received_endpoint(
    data: OperationRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await record_prescription_received(supabase, user.user_id, data)


@router.post("/undo", response_model=OperationResultDTO)
async def undo_endpoint(
    data: UndoOperationRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await undo_operation(supabase, user.user_id, data)
