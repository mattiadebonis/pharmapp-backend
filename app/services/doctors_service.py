from uuid import UUID

from fastapi import HTTPException, status
from supabase import Client


async def list_doctors(supabase: Client, user_id: UUID) -> list[dict]:
    """List all doctors belonging to the user."""
    result = (
        supabase.table("doctors")
        .select("*")
        .eq("user_id", str(user_id))
        .execute()
    )
    return result.data


async def create_doctor(supabase: Client, user_id: UUID, data) -> dict:
    """Create a new doctor for the user."""
    payload = data.model_dump(exclude_none=True)
    payload["user_id"] = str(user_id)
    result = supabase.table("doctors").insert(payload).execute()
    return result.data[0]


async def get_doctor(supabase: Client, user_id: UUID, doctor_id: UUID) -> dict:
    """Get a single doctor, verifying ownership."""
    result = (
        supabase.table("doctors")
        .select("*")
        .eq("id", str(doctor_id))
        .eq("user_id", str(user_id))
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "Doctor not found"}},
        )
    return result.data[0]


async def update_doctor(supabase: Client, user_id: UUID, doctor_id: UUID, data) -> dict:
    """Update a doctor, verifying ownership."""
    payload = data.model_dump(exclude_none=True)
    if not payload:
        return await get_doctor(supabase, user_id, doctor_id)
    result = (
        supabase.table("doctors")
        .update(payload)
        .eq("id", str(doctor_id))
        .eq("user_id", str(user_id))
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "Doctor not found"}},
        )
    return result.data[0]


async def delete_doctor(supabase: Client, user_id: UUID, doctor_id: UUID) -> None:
    """Delete a doctor, verifying ownership."""
    result = (
        supabase.table("doctors")
        .delete()
        .eq("id", str(doctor_id))
        .eq("user_id", str(user_id))
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "Doctor not found"}},
        )
