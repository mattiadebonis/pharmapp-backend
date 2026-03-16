from uuid import UUID

from fastapi import HTTPException, status
from supabase import Client


async def assert_owner(supabase: Client, user_id: UUID, table: str, record_id: UUID) -> None:
    """Verify the authenticated user owns the record. Raises 403 if not."""
    result = supabase.table(table).select("owner_user_id").eq("id", str(record_id)).maybe_single().execute()
    if not result or not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "Resource not found"}},
        )
    if result.data["owner_user_id"] != str(user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "forbidden", "message": "Access denied"}},
        )


async def user_can_access_cabinet(supabase: Client, user_id: UUID, cabinet_id: UUID) -> bool:
    """Check if user owns the cabinet or has an active membership."""
    cabinet = supabase.table("cabinets").select("owner_user_id").eq("id", str(cabinet_id)).maybe_single().execute()
    if not cabinet or not cabinet.data:
        return False
    if cabinet.data["owner_user_id"] == str(user_id):
        return True
    membership = (
        supabase.table("cabinet_memberships")
        .select("id")
        .eq("cabinet_id", str(cabinet_id))
        .eq("user_id", str(user_id))
        .eq("status", "active")
        .maybe_single()
        .execute()
    )
    return membership is not None and membership.data is not None


async def user_can_access_tracked_medicine(supabase: Client, user_id: UUID, medicine_id: UUID) -> bool:
    """Check if user owns the medicine or can access its cabinet."""
    med = (
        supabase.table("tracked_medicines")
        .select("owner_user_id, cabinet_id")
        .eq("id", str(medicine_id))
        .maybe_single()
        .execute()
    )
    if not med or not med.data:
        return False
    if med.data["owner_user_id"] == str(user_id):
        return True
    if med.data.get("cabinet_id"):
        return await user_can_access_cabinet(supabase, user_id, UUID(med.data["cabinet_id"]))
    return False


async def assert_can_access_tracked_medicine(supabase: Client, user_id: UUID, medicine_id: UUID) -> None:
    """Raises 403 if user cannot access the tracked medicine."""
    if not await user_can_access_tracked_medicine(supabase, user_id, medicine_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "forbidden", "message": "Access denied"}},
        )
