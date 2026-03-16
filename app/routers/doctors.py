from uuid import UUID

from fastapi import APIRouter, Depends, status
from supabase import Client

from app.auth.models import AuthenticatedUser
from app.dependencies import get_current_user, get_supabase
from app.schemas.doctor import DoctorCreateRequest, DoctorDTO, DoctorUpdateRequest
from app.services.doctors_service import create_doctor, delete_doctor, get_doctor, list_doctors, update_doctor

router = APIRouter(prefix="/doctors", tags=["Doctors"])


@router.get("", response_model=list[DoctorDTO])
async def list_doctors_endpoint(
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await list_doctors(supabase, user.user_id)


@router.post("", response_model=DoctorDTO, status_code=status.HTTP_201_CREATED)
async def create_doctor_endpoint(
    data: DoctorCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await create_doctor(supabase, user.user_id, data)


@router.get("/{doctor_id}", response_model=DoctorDTO)
async def get_doctor_endpoint(
    doctor_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await get_doctor(supabase, user.user_id, doctor_id)


@router.put("/{doctor_id}", response_model=DoctorDTO)
async def update_doctor_endpoint(
    doctor_id: UUID,
    data: DoctorUpdateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await update_doctor(supabase, user.user_id, doctor_id, data)


@router.delete("/{doctor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_doctor_endpoint(
    doctor_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    await delete_doctor(supabase, user.user_id, doctor_id)
