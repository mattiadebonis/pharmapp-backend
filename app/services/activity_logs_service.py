from datetime import datetime
from uuid import UUID

from fastapi import HTTPException, status
from supabase import Client


async def create_log(supabase: Client, user_id: UUID, data) -> dict:
    """Create an activity log entry."""
    payload = data.model_dump(exclude_none=True)
    payload["user_id"] = str(user_id)
    # Convert UUID fields to strings
    for uuid_field in ("profile_id", "medication_id"):
        if payload.get(uuid_field):
            payload[uuid_field] = str(payload[uuid_field])
    # Convert datetime fields
    if "created_at" in payload and hasattr(payload["created_at"], "isoformat"):
        payload["created_at"] = payload["created_at"].isoformat()
    payload["actor_user_id"] = str(user_id)
    result = supabase.table("activity_logs").insert(payload).execute()
    return result.data[0]


async def list_logs(
    supabase: Client,
    user_id: UUID,
    *,
    medication_id: UUID | None = None,
    profile_id: UUID | None = None,
    action_type: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """List activity logs with optional filters and pagination.

    Returns a tuple of ``(logs, total_count)``.
    """
    query = (
        supabase.table("activity_logs")
        .select("*", count="exact")
        .eq("user_id", str(user_id))
    )
    if medication_id:
        query = query.eq("medication_id", str(medication_id))
    if profile_id:
        query = query.eq("profile_id", str(profile_id))
    if action_type:
        query = query.eq("action_type", action_type)
    if since:
        query = query.gte("created_at", since.isoformat())
    if until:
        query = query.lte("created_at", until.isoformat())

    query = query.order("created_at", desc=True).range(offset, offset + limit - 1)
    result = query.execute()
    total = result.count or 0
    return result.data, total


async def get_log(supabase: Client, user_id: UUID, log_id: UUID) -> dict:
    """Get a single activity log entry, verifying ownership."""
    result = (
        supabase.table("activity_logs")
        .select("*")
        .eq("id", str(log_id))
        .eq("user_id", str(user_id))
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "Activity log not found"}},
        )
    return result.data[0]
