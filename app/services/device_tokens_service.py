from uuid import UUID

from fastapi import HTTPException, status
from supabase import Client


async def register_token(
    supabase: Client,
    user_id: UUID,
    token: str,
    platform: str,
) -> dict:
    """Register a device token for push notifications.

    If the same ``token`` already exists for this user, the existing row is
    returned (upsert-like behaviour based on the UNIQUE constraint on
    ``token``).
    """
    uid = str(user_id)

    # Check if this exact token already exists (for any user)
    existing = (
        supabase.table("device_tokens")
        .select("*")
        .eq("token", token)
        .execute()
    )
    if existing.data:
        row = existing.data[0]
        if row["user_id"] == uid:
            # Same user, same token -> just return it
            return row
        # Token belongs to another user -> reassign to current user
        result = (
            supabase.table("device_tokens")
            .update({"user_id": uid, "platform": platform})
            .eq("id", row["id"])
            .execute()
        )
        return result.data[0]

    # Insert new token
    result = (
        supabase.table("device_tokens")
        .insert({
            "user_id": uid,
            "token": token,
            "platform": platform,
        })
        .execute()
    )
    return result.data[0]


async def remove_token(
    supabase: Client,
    user_id: UUID,
    token: str,
) -> None:
    """Remove a device token.

    Only the owning user can remove a token.
    """
    result = (
        supabase.table("device_tokens")
        .delete()
        .eq("token", token)
        .eq("user_id", str(user_id))
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "Device token not found"}},
        )


async def remove_token_by_id(
    supabase: Client,
    user_id: UUID,
    token_id: UUID,
) -> None:
    """Remove a device token by its ID."""
    result = (
        supabase.table("device_tokens")
        .delete()
        .eq("id", str(token_id))
        .eq("user_id", str(user_id))
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "Device token not found"}},
        )


async def list_tokens(supabase: Client, user_id: UUID) -> list[dict]:
    """List all device tokens for the user."""
    result = (
        supabase.table("device_tokens")
        .select("*")
        .eq("user_id", str(user_id))
        .execute()
    )
    return result.data
