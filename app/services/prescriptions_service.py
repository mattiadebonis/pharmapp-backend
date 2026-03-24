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


async def list_prescriptions(
    supabase: Client, user_id: UUID, medication_id: UUID
) -> list[dict]:
    """List all prescriptions for a medication (verifying ownership)."""
    await _verify_medication_ownership(supabase, user_id, medication_id)
    result = (
        supabase.table("prescriptions")
        .select("*")
        .eq("medication_id", str(medication_id))
        .order("issued_date", desc=True)
        .execute()
    )
    return result.data


async def create_prescription(
    supabase: Client, user_id: UUID, medication_id: UUID, data
) -> dict:
    """Create a prescription for a medication."""
    await _verify_medication_ownership(supabase, user_id, medication_id)
    payload = data.model_dump(exclude_none=True)
    payload["medication_id"] = str(medication_id)
    # Convert date fields to ISO strings if they are date objects
    for date_field in ("issued_date", "expiry_date"):
        if date_field in payload and hasattr(payload[date_field], "isoformat"):
            payload[date_field] = payload[date_field].isoformat()
    # Convert doctor_id to string if present
    if payload.get("doctor_id"):
        payload["doctor_id"] = str(payload["doctor_id"])
    result = supabase.table("prescriptions").insert(payload).execute()
    return result.data[0]


async def get_prescription(
    supabase: Client, user_id: UUID, medication_id: UUID, prescription_id: UUID
) -> dict:
    """Get a single prescription, verifying medication ownership."""
    await _verify_medication_ownership(supabase, user_id, medication_id)
    result = (
        supabase.table("prescriptions")
        .select("*")
        .eq("id", str(prescription_id))
        .eq("medication_id", str(medication_id))
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "Prescription not found"}},
        )
    return result.data[0]


async def update_prescription(
    supabase: Client,
    user_id: UUID,
    medication_id: UUID,
    prescription_id: UUID,
    data,
) -> dict:
    """Update a prescription, verifying medication ownership."""
    await _verify_medication_ownership(supabase, user_id, medication_id)
    payload = data.model_dump(exclude_none=True)
    if not payload:
        return await get_prescription(supabase, user_id, medication_id, prescription_id)
    # Convert date fields to ISO strings if they are date objects
    for date_field in ("issued_date", "expiry_date"):
        if date_field in payload and hasattr(payload[date_field], "isoformat"):
            payload[date_field] = payload[date_field].isoformat()
    if "doctor_id" in payload and payload["doctor_id"]:
        payload["doctor_id"] = str(payload["doctor_id"])
    result = (
        supabase.table("prescriptions")
        .update(payload)
        .eq("id", str(prescription_id))
        .eq("medication_id", str(medication_id))
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "Prescription not found"}},
        )
    return result.data[0]


async def delete_prescription(
    supabase: Client, user_id: UUID, medication_id: UUID, prescription_id: UUID
) -> None:
    """Delete a prescription, verifying medication ownership."""
    await _verify_medication_ownership(supabase, user_id, medication_id)
    result = (
        supabase.table("prescriptions")
        .delete()
        .eq("id", str(prescription_id))
        .eq("medication_id", str(medication_id))
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "Prescription not found"}},
        )
