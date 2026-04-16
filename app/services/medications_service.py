from uuid import UUID

from fastapi import HTTPException, status
from supabase import Client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_profile_ids(supabase: Client, user_id: UUID) -> list[str]:
    """Return all profile IDs that belong to the given user."""
    profiles_result = (
        supabase.table("profiles")
        .select("id")
        .eq("user_id", str(user_id))
        .execute()
    )
    return [p["id"] for p in profiles_result.data]


async def _verify_medication_ownership(
    supabase: Client, user_id: UUID, medication_id: UUID
) -> dict:
    """Verify the medication belongs to the user (via profile). Returns the row."""
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
    return med.data[0]


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


async def list_medications(supabase: Client, user_id: UUID) -> list[dict]:
    """List all medications for the user (across all their profiles)."""
    profile_ids = await _get_profile_ids(supabase, user_id)
    if not profile_ids:
        return []
    result = (
        supabase.table("medications")
        .select("*")
        .in_("profile_id", profile_ids)
        .execute()
    )
    return result.data


async def create_medication(supabase: Client, user_id: UUID, data) -> dict:
    """Create a new medication.

    The request body must include ``profile_id``.  Ownership of that profile
    is verified before inserting.
    """
    payload = data.model_dump(exclude_none=True)
    profile_id = payload.get("profile_id")
    if not profile_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "bad_request", "message": "profile_id is required"}},
        )
    # Verify the profile belongs to the user
    profile_check = (
        supabase.table("profiles")
        .select("id")
        .eq("id", str(profile_id))
        .eq("user_id", str(user_id))
        .execute()
    )
    if not profile_check.data:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "forbidden", "message": "Profile does not belong to user"}},
        )
    payload["profile_id"] = str(profile_id)
    if payload.get("prescribing_doctor_id"):
        payload["prescribing_doctor_id"] = str(payload["prescribing_doctor_id"])
    result = supabase.table("medications").insert(payload).execute()
    return result.data[0]


async def get_medication(supabase: Client, user_id: UUID, medication_id: UUID) -> dict:
    """Get a single medication, verifying ownership through the profile chain."""
    row = await _verify_medication_ownership(supabase, user_id, medication_id)
    # Strip the joined profiles data before returning
    row.pop("profiles", None)
    return row


async def get_medication_with_details(
    supabase: Client, user_id: UUID, medication_id: UUID
) -> dict:
    """Get a medication with its dosing schedule, supply, and prescriptions."""
    row = await _verify_medication_ownership(supabase, user_id, medication_id)
    row.pop("profiles", None)
    mid = str(medication_id)

    schedule_r = (
        supabase.table("dosing_schedules")
        .select("*")
        .eq("medication_id", mid)
        .execute()
    )
    supply_r = (
        supabase.table("supplies")
        .select("*")
        .eq("medication_id", mid)
        .execute()
    )
    prescriptions_r = (
        supabase.table("prescriptions")
        .select("*")
        .eq("medication_id", mid)
        .execute()
    )

    return {
        **row,
        "schedules": schedule_r.data,
        "supply": supply_r.data[0] if supply_r.data else None,
        "prescriptions": prescriptions_r.data,
    }


async def update_medication(
    supabase: Client, user_id: UUID, medication_id: UUID, data
) -> dict:
    """Update a medication, verifying ownership."""
    await _verify_medication_ownership(supabase, user_id, medication_id)
    payload = data.model_dump(exclude_none=True)
    if not payload:
        return await get_medication(supabase, user_id, medication_id)
    if "prescribing_doctor_id" in payload and payload["prescribing_doctor_id"]:
        payload["prescribing_doctor_id"] = str(payload["prescribing_doctor_id"])
    if "profile_id" in payload and payload["profile_id"]:
        payload["profile_id"] = str(payload["profile_id"])
    result = (
        supabase.table("medications")
        .update(payload)
        .eq("id", str(medication_id))
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "Medication not found"}},
        )
    return result.data[0]


async def delete_medication(
    supabase: Client, user_id: UUID, medication_id: UUID
) -> None:
    """Delete a medication, verifying ownership.

    CASCADE in the DB will remove dosing_schedules, supplies, prescriptions,
    and dose_events linked to this medication.
    """
    await _verify_medication_ownership(supabase, user_id, medication_id)
    result = (
        supabase.table("medications")
        .delete()
        .eq("id", str(medication_id))
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "Medication not found"}},
        )
