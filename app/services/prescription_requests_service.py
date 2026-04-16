from datetime import datetime, timezone
from uuid import UUID, uuid4

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
        .select("id, profiles!inner(user_id)")
        .eq("id", str(medication_id))
        .execute()
    )
    if not med.data or med.data[0]["profiles"]["user_id"] != str(user_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "Medication not found"}},
        )


def _stringify_uuid(payload: dict, key: str) -> None:
    """Convert a UUID value in a payload dict to its string form in-place."""
    if payload.get(key):
        payload[key] = str(payload[key])


def _stringify_datetime(payload: dict, key: str) -> None:
    """Convert a datetime value in a payload dict to ISO-8601 string in-place."""
    value = payload.get(key)
    if value is not None and hasattr(value, "isoformat"):
        payload[key] = value.isoformat()


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


async def list_prescription_requests(
    supabase: Client, user_id: UUID, medication_id: UUID
) -> list[dict]:
    """List all prescription requests for a medication (verifying ownership)."""
    await _verify_medication_ownership(supabase, user_id, medication_id)
    result = (
        supabase.table("prescription_requests")
        .select("*")
        .eq("medication_id", str(medication_id))
        .order("sent_at", desc=True)
        .execute()
    )
    return result.data


async def create_prescription_request(
    supabase: Client, user_id: UUID, medication_id: UUID, data
) -> dict:
    """Create a prescription request for a medication."""
    await _verify_medication_ownership(supabase, user_id, medication_id)
    payload = data.model_dump(exclude_none=True)
    payload["medication_id"] = str(medication_id)
    # Client-generated id enables offline-queue idempotency. Fallback here if missing.
    if not payload.get("id"):
        payload["id"] = str(uuid4())
    else:
        payload["id"] = str(payload["id"])
    if not payload.get("sent_at"):
        payload["sent_at"] = datetime.now(timezone.utc).isoformat()
    _stringify_uuid(payload, "doctor_id")
    _stringify_datetime(payload, "sent_at")
    _stringify_datetime(payload, "purchased_at")
    # Default status if the client didn't send one.
    payload.setdefault("status", "pending")
    result = supabase.table("prescription_requests").insert(payload).execute()
    return result.data[0]


async def get_prescription_request(
    supabase: Client,
    user_id: UUID,
    medication_id: UUID,
    request_id: UUID,
) -> dict:
    """Get a single prescription request, verifying medication ownership."""
    await _verify_medication_ownership(supabase, user_id, medication_id)
    result = (
        supabase.table("prescription_requests")
        .select("*")
        .eq("id", str(request_id))
        .eq("medication_id", str(medication_id))
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {"code": "not_found", "message": "Prescription request not found"}
            },
        )
    return result.data[0]


async def update_prescription_request(
    supabase: Client,
    user_id: UUID,
    medication_id: UUID,
    request_id: UUID,
    data,
) -> dict:
    """Update a prescription request (typically status -> purchased | cancelled)."""
    await _verify_medication_ownership(supabase, user_id, medication_id)
    payload = data.model_dump(exclude_none=True)
    if not payload:
        return await get_prescription_request(
            supabase, user_id, medication_id, request_id
        )
    # If the client promotes the record to purchased without providing a timestamp,
    # stamp it server-side so the history is coherent.
    if payload.get("status") == "purchased" and not payload.get("purchased_at"):
        payload["purchased_at"] = datetime.now(timezone.utc).isoformat()
    _stringify_uuid(payload, "doctor_id")
    _stringify_datetime(payload, "purchased_at")
    result = (
        supabase.table("prescription_requests")
        .update(payload)
        .eq("id", str(request_id))
        .eq("medication_id", str(medication_id))
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {"code": "not_found", "message": "Prescription request not found"}
            },
        )
    return result.data[0]
