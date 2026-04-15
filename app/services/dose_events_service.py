from datetime import datetime
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


async def _verify_dose_event_ownership(
    supabase: Client, user_id: UUID, event_id: UUID
) -> dict:
    """Verify the dose event belongs to the user via the profile chain."""
    event = (
        supabase.table("dose_events")
        .select("*, profiles!inner(user_id)")
        .eq("id", str(event_id))
        .execute()
    )
    if not event.data or event.data[0]["profiles"]["user_id"] != str(user_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "Dose event not found"}},
        )
    return event.data[0]


# ---------------------------------------------------------------------------
# CRUD + filtered listing
# ---------------------------------------------------------------------------


async def list_dose_events(
    supabase: Client,
    user_id: UUID,
    *,
    medication_id: UUID | None = None,
    profile_id: UUID | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    event_status: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[dict]:
    """List dose events with optional filters.

    Filters:
    - ``medication_id``: only events for this medication
    - ``profile_id``: only events for this profile (must belong to user)
    - ``since`` / ``until``: date range on ``due_at``
    - ``event_status``: one of pending, taken, missed, skipped, snoozed
    """
    # Determine which profile IDs the user owns
    profile_ids = await _get_profile_ids(supabase, user_id)
    if not profile_ids:
        return []

    # If a specific profile_id is provided, verify it belongs to the user
    if profile_id:
        pid = str(profile_id)
        if pid not in profile_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "forbidden", "message": "Profile does not belong to user"}},
            )
        query = supabase.table("dose_events").select("*").eq("profile_id", pid)
    else:
        query = supabase.table("dose_events").select("*").in_("profile_id", profile_ids)

    if medication_id:
        query = query.eq("medication_id", str(medication_id))
    if since:
        query = query.gte("due_at", since.isoformat())
    if until:
        query = query.lte("due_at", until.isoformat())
    if event_status:
        query = query.eq("status", event_status)

    query = query.order("due_at", desc=True).range(offset, offset + limit - 1)
    result = query.execute()
    return result.data


async def create_dose_event(supabase: Client, user_id: UUID, data) -> dict:
    """Create a dose event.

    The ``profile_id`` in the payload must belong to the user.
    """
    payload = data.model_dump(exclude_none=True)
    # Verify profile ownership
    profile_id = payload.get("profile_id")
    if not profile_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "bad_request", "message": "profile_id is required"}},
        )
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
    # Convert UUID fields to strings
    for uuid_field in ("profile_id", "medication_id", "dosing_schedule_id"):
        if payload.get(uuid_field):
            payload[uuid_field] = str(payload[uuid_field])
    # Convert datetime fields to ISO strings
    for dt_field in ("due_at", "taken_at", "auto_registered_at", "user_corrected_at"):
        if dt_field in payload and hasattr(payload[dt_field], "isoformat"):
            payload[dt_field] = payload[dt_field].isoformat()
    payload["actor_user_id"] = str(user_id)
    result = supabase.table("dose_events").insert(payload).execute()
    return result.data[0]


async def get_dose_event(supabase: Client, user_id: UUID, event_id: UUID) -> dict:
    """Get a single dose event, verifying ownership through the profile chain."""
    row = await _verify_dose_event_ownership(supabase, user_id, event_id)
    row.pop("profiles", None)
    return row


async def update_dose_event(
    supabase: Client, user_id: UUID, event_id: UUID, data
) -> dict:
    """Update a dose event (e.g. mark as taken/missed/skipped)."""
    await _verify_dose_event_ownership(supabase, user_id, event_id)
    payload = data.model_dump(exclude_none=True)
    if not payload:
        return await get_dose_event(supabase, user_id, event_id)
    # Convert datetime fields
    for dt_field in ("taken_at", "auto_registered_at", "user_corrected_at"):
        if dt_field in payload and hasattr(payload[dt_field], "isoformat"):
            payload[dt_field] = payload[dt_field].isoformat()
    payload["actor_user_id"] = str(user_id)
    result = (
        supabase.table("dose_events")
        .update(payload)
        .eq("id", str(event_id))
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "Dose event not found"}},
        )
    return result.data[0]


async def delete_dose_event(
    supabase: Client, user_id: UUID, event_id: UUID
) -> None:
    """Delete a dose event, verifying ownership."""
    await _verify_dose_event_ownership(supabase, user_id, event_id)
    result = (
        supabase.table("dose_events")
        .delete()
        .eq("id", str(event_id))
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "Dose event not found"}},
        )
