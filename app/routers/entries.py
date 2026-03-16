from uuid import UUID

from fastapi import APIRouter, Depends, status
from supabase import Client

from app.auth.models import AuthenticatedUser
from app.dependencies import get_current_user, get_supabase
from app.schemas.entry import MedicineEntryCreateRequest, MedicineEntryDTO, MedicineEntryUpdateRequest
from app.services.entries_service import create_entry, delete_entry, list_entries, update_entry

router = APIRouter(prefix="/medicines/{medicine_id}/entries", tags=["Medicine Entries"])


@router.get("", response_model=list[MedicineEntryDTO])
async def list_entries_endpoint(
    medicine_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await list_entries(supabase, user.user_id, medicine_id)


@router.post("", response_model=MedicineEntryDTO, status_code=status.HTTP_201_CREATED)
async def create_entry_endpoint(
    medicine_id: UUID,
    data: MedicineEntryCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await create_entry(supabase, user.user_id, medicine_id, data)


@router.put("/{entry_id}", response_model=MedicineEntryDTO)
async def update_entry_endpoint(
    medicine_id: UUID,
    entry_id: UUID,
    data: MedicineEntryUpdateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await update_entry(supabase, user.user_id, medicine_id, entry_id, data)


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entry_endpoint(
    medicine_id: UUID,
    entry_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    await delete_entry(supabase, user.user_id, medicine_id, entry_id)
