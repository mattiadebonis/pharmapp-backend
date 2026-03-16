from uuid import UUID

from fastapi import APIRouter, Depends, status
from supabase import Client

from app.auth.models import AuthenticatedUser
from app.dependencies import get_current_user, get_supabase
from app.schemas.person import PersonCreateRequest, PersonDTO, PersonUpdateRequest
from app.services.people_service import create_person, delete_person, get_person, list_people, update_person

router = APIRouter(prefix="/people", tags=["People"])


@router.get("", response_model=list[PersonDTO])
async def list_people_endpoint(
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await list_people(supabase, user.user_id)


@router.post("", response_model=PersonDTO, status_code=status.HTTP_201_CREATED)
async def create_person_endpoint(
    data: PersonCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await create_person(supabase, user.user_id, data)


@router.get("/{person_id}", response_model=PersonDTO)
async def get_person_endpoint(
    person_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await get_person(supabase, user.user_id, person_id)


@router.put("/{person_id}", response_model=PersonDTO)
async def update_person_endpoint(
    person_id: UUID,
    data: PersonUpdateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await update_person(supabase, user.user_id, person_id, data)


@router.delete("/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_person_endpoint(
    person_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    await delete_person(supabase, user.user_id, person_id)
