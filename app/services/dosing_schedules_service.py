from uuid import UUID

from fastapi import HTTPException, status
from supabase import Client

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _verify_medication_ownership(
    supabase: Client, user_id: UUID, medication_id: UUID
) -> None:
    """Verify the medication belongs to the user via the profile chain."""
    med = (
        supabase.table("medications")
        .select("*, profiles!inner(user_id)")
        .eq("id", str(medication_id))
        .execute()
    )
    if not med.data or med.data[0]["profiles"]["user_id"] != str(user_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "Medication not found"}},
        )


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


async def get_dosing_schedule(
    supabase: Client, user_id: UUID, medication_id: UUID, schedule_id: UUID
) -> dict:
    """Get a single dosing schedule, verifying medication ownership."""
    await _verify_medication_ownership(supabase, user_id, medication_id)
    result = (
        supabase.table("dosing_schedules")
        .select("*")
        .eq("id", str(schedule_id))
        .eq("medication_id", str(medication_id))
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "Dosing schedule not found"}},
        )
    return result.data[0]


async def update_dosing_schedule(
    supabase: Client,
    user_id: UUID,
    medication_id: UUID,
    schedule_id: UUID,
    data,
) -> dict:
    """Update a dosing schedule, verifying medication ownership."""
    await _verify_medication_ownership(supabase, user_id, medication_id)
    payload = data.model_dump(exclude_none=True, mode="json")
    if not payload:
        return await get_dosing_schedule(supabase, user_id, medication_id, schedule_id)
    result = (
        supabase.table("dosing_schedules")
        .update(payload)
        .eq("id", str(schedule_id))
        .eq("medication_id", str(medication_id))
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "Dosing schedule not found"}},
        )
    return result.data[0]
