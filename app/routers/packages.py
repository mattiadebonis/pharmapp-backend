from uuid import UUID

from fastapi import APIRouter, Depends
from supabase import Client

from app.auth.models import AuthenticatedUser
from app.dependencies import get_current_user, get_supabase
from app.schemas.medication_package import MedicationPackageDTO, PackagesReplaceRequest
from app.services.packages_service import replace_packages

router = APIRouter(prefix="/medications/{medication_id}/packages", tags=["Packages"])


@router.put("", response_model=list[MedicationPackageDTO])
async def replace_packages_endpoint(
    medication_id: UUID,
    data: PackagesReplaceRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await replace_packages(supabase, user.user_id, medication_id, data)
