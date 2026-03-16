from uuid import UUID

from fastapi import APIRouter, Depends, status
from supabase import Client

from app.auth.models import AuthenticatedUser
from app.dependencies import get_current_user, get_supabase
from app.schemas.medicine import (
    CabinetMoveRequest,
    CreateMedicineFromCatalogRequest,
    LabelsUpdateRequest,
    MedicineUpdateRequest,
    PackageCreateRequest,
    StockThresholdUpdateRequest,
    TrackedMedicineDTO,
    TrackedMedicineWithPackagesDTO,
    TrackedPackageDTO,
)
from app.services.medicines_service import (
    create_medicine,
    create_package,
    delete_medicine,
    delete_package,
    get_medicine_detail,
    list_medicines,
    move_to_cabinet,
    update_labels,
    update_medicine,
    update_stock_threshold,
)

router = APIRouter(prefix="/medicines", tags=["Medicines"])


@router.get("", response_model=list[TrackedMedicineWithPackagesDTO])
async def list_medicines_endpoint(
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await list_medicines(supabase, user.user_id)


@router.post("", response_model=TrackedMedicineWithPackagesDTO, status_code=status.HTTP_201_CREATED)
async def create_medicine_endpoint(
    data: CreateMedicineFromCatalogRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await create_medicine(supabase, user.user_id, data)


@router.get("/{medicine_id}", response_model=TrackedMedicineWithPackagesDTO)
async def get_medicine_endpoint(
    medicine_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await get_medicine_detail(supabase, user.user_id, medicine_id)


@router.put("/{medicine_id}", response_model=TrackedMedicineDTO)
async def update_medicine_endpoint(
    medicine_id: UUID,
    data: MedicineUpdateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await update_medicine(supabase, user.user_id, medicine_id, data)


@router.delete("/{medicine_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_medicine_endpoint(
    medicine_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    await delete_medicine(supabase, user.user_id, medicine_id)


@router.put("/{medicine_id}/labels", response_model=TrackedMedicineDTO)
async def update_labels_endpoint(
    medicine_id: UUID,
    data: LabelsUpdateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await update_labels(supabase, user.user_id, medicine_id, data)


@router.put("/{medicine_id}/stock-threshold", response_model=TrackedMedicineDTO)
async def update_stock_threshold_endpoint(
    medicine_id: UUID,
    data: StockThresholdUpdateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await update_stock_threshold(supabase, user.user_id, medicine_id, data)


@router.put("/{medicine_id}/cabinet", response_model=TrackedMedicineDTO)
async def move_to_cabinet_endpoint(
    medicine_id: UUID,
    data: CabinetMoveRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await move_to_cabinet(supabase, user.user_id, medicine_id, data)


@router.post("/{medicine_id}/packages", response_model=TrackedPackageDTO, status_code=status.HTTP_201_CREATED)
async def create_package_endpoint(
    medicine_id: UUID,
    data: PackageCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await create_package(supabase, user.user_id, medicine_id, data)


@router.delete("/{medicine_id}/packages/{package_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_package_endpoint(
    medicine_id: UUID,
    package_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    await delete_package(supabase, user.user_id, medicine_id, package_id)
