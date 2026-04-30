from uuid import UUID

from fastapi import HTTPException, status
from supabase import Client


# Default values matching the DB schema defaults
_DEFAULTS = {
    "catalog_country": "it",
    "default_refill_threshold": 7,
    "default_tracking_mode": "passive",
    "default_snooze_minutes": 10,
    "grace_minutes": 120,
    "notify_caregivers": True,
    "notifications_enabled": True,
    "refill_alerts_enabled": True,
    "biometrics_enabled": False,
    "face_id_sensitive_actions": False,
    "anonymous_notifications": False,
    "hide_medication_names": False,
}


async def get_or_create_settings(supabase: Client, user_id: UUID) -> dict:
    """Get user settings, creating a default row if none exists.

    The ``user_settings`` table uses ``user_id`` as the primary key, so there
    is exactly zero or one row per user.
    """
    uid = str(user_id)
    result = (
        supabase.table("user_settings")
        .select("*")
        .eq("user_id", uid)
        .execute()
    )
    if result.data:
        return result.data[0]

    # Create default settings
    payload = {"user_id": uid, **_DEFAULTS}
    insert_result = supabase.table("user_settings").insert(payload).execute()
    return insert_result.data[0]


async def update_settings(supabase: Client, user_id: UUID, data) -> dict:
    """Update user settings.

    If no settings row exists yet, one is created first.
    """
    uid = str(user_id)
    payload = data.model_dump(exclude_none=True)
    if not payload:
        return await get_or_create_settings(supabase, user_id)

    # Ensure the row exists
    await get_or_create_settings(supabase, user_id)

    result = (
        supabase.table("user_settings")
        .update(payload)
        .eq("user_id", uid)
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "Settings not found"}},
        )
    return result.data[0]
