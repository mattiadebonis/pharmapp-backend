"""Shared ownership helpers used by every CRUD service.

Centralises the `profile.user_id == auth_user_id` check so we don't have
copies of `_verify_*_ownership` scattered across every service file.
Each helper raises `HTTPException` with the conventional `{error: {code,
message}}` shape on failure.
"""

from uuid import UUID

from fastapi import HTTPException, status
from supabase import Client


def _not_found(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error": {"code": "not_found", "message": message}},
    )


def _forbidden(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"error": {"code": "forbidden", "message": message}},
    )


def _conflict(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"error": {"code": "conflict", "message": message}},
    )


async def assert_profile_owned(
    supabase: Client, user_id: UUID, profile_id: UUID
) -> None:
    """Raise 403 if the profile does not belong to the user."""
    res = (
        supabase.table("profiles")
        .select("id")
        .eq("id", str(profile_id))
        .eq("user_id", str(user_id))
        .execute()
    )
    if not res.data:
        raise _forbidden("Profile does not belong to user")


async def get_owned_profile_ids(supabase: Client, user_id: UUID) -> list[str]:
    """Return all profile ids owned by the user."""
    res = (
        supabase.table("profiles")
        .select("id")
        .eq("user_id", str(user_id))
        .execute()
    )
    return [row["id"] for row in res.data]


async def assert_medication_owned(
    supabase: Client, user_id: UUID, medication_id: UUID
) -> dict:
    """Return the medication row if the user owns it via profile, else 404."""
    res = (
        supabase.table("medications")
        .select("*, profiles!inner(user_id)")
        .eq("id", str(medication_id))
        .execute()
    )
    if not res.data or res.data[0]["profiles"]["user_id"] != str(user_id):
        raise _not_found("Medication not found")
    row = res.data[0]
    row.pop("profiles", None)
    return row


async def log_activity(
    supabase: Client,
    user_id: UUID,
    action_type: str,
    *,
    profile_id: UUID | str | None = None,
    medication_id: UUID | str | None = None,
    details: dict | None = None,
) -> None:
    """Best-effort activity log insert. Failures are swallowed because
    audit logging must not break the surrounding mutation."""
    try:
        payload: dict = {
            "user_id": str(user_id),
            "actor_user_id": str(user_id),
            "action_type": action_type,
        }
        if profile_id is not None:
            payload["profile_id"] = str(profile_id)
        if medication_id is not None:
            payload["medication_id"] = str(medication_id)
        if details is not None:
            payload["details"] = details
        supabase.table("activity_logs").insert(payload).execute()
    except Exception:
        pass


async def assert_routine_owned(
    supabase: Client, user_id: UUID, routine_id: UUID
) -> dict:
    """Return the routine row if the user owns it, else 404."""
    res = (
        supabase.table("routines")
        .select("*, profiles!inner(user_id)")
        .eq("id", str(routine_id))
        .execute()
    )
    if not res.data or res.data[0]["profiles"]["user_id"] != str(user_id):
        raise _not_found("Routine not found")
    row = res.data[0]
    row.pop("profiles", None)
    return row
