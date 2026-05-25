from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status
from supabase import Client


async def list_profiles(supabase: Client, user_id: UUID) -> list[dict]:
    """List all profiles belonging to the user."""
    result = (
        supabase.table("profiles")
        .select("*")
        .eq("user_id", str(user_id))
        .execute()
    )
    return result.data


async def create_profile(supabase: Client, user_id: UUID, data) -> dict:
    """Create a new profile for the user. Client-provided `id` enables
    idempotent offline-queue retries — without it, backend assigns a
    new UUID and child records (medications, dose_events) referencing
    the local UUID would FK-fail."""
    payload = data.model_dump(exclude_none=True, mode="json")
    payload["user_id"] = str(user_id)
    if payload.get("id"):
        payload["id"] = str(payload["id"]).lower()
        result = supabase.table("profiles").upsert(payload, on_conflict="id").execute()
    else:
        result = supabase.table("profiles").insert(payload).execute()
    return result.data[0]


async def get_profile(supabase: Client, user_id: UUID, profile_id: UUID) -> dict:
    """Get a single profile, verifying ownership."""
    result = (
        supabase.table("profiles")
        .select("*")
        .eq("id", str(profile_id))
        .eq("user_id", str(user_id))
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "Profile not found"}},
        )
    return result.data[0]


async def get_own_profile(supabase: Client, user_id: UUID) -> dict:
    """Get the user's own profile (profile_type='own')."""
    result = (
        supabase.table("profiles")
        .select("*")
        .eq("user_id", str(user_id))
        .eq("profile_type", "own")
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "Own profile not found"}},
        )
    return result.data[0]


async def init_own_profile(
    supabase: Client,
    user_id: UUID,
    display_name: str = "Io",
    color: str = "#2B7DD4",
) -> dict:
    """Idempotent provisioning of the user's own profile.

    The iOS onboarding flow calls this once after the user has completed
    the setup screens. Calling it again returns the existing profile
    instead of creating a duplicate — important because the offline
    queue may replay the request after a transient network failure.

    Replaces the implicit auto-create that ``get_bootstrap_data`` used
    to perform: that path masked Supabase anonymous-session rotation by
    silently spawning empty profiles, which then wiped the iOS cache.
    """
    existing = (
        supabase.table("profiles")
        .select("*")
        .eq("user_id", str(user_id))
        .eq("profile_type", "own")
        .execute()
    )
    if existing.data:
        return existing.data[0]

    created = (
        supabase.table("profiles")
        .insert({
            "user_id": str(user_id),
            "display_name": display_name,
            "profile_type": "own",
            "color": color,
        })
        .execute()
    )
    return created.data[0]


async def update_profile(supabase: Client, user_id: UUID, profile_id: UUID, data) -> dict:
    """Update a profile, verifying ownership."""
    payload = data.model_dump(exclude_none=True, mode="json")
    if not payload:
        return await get_profile(supabase, user_id, profile_id)
    result = (
        supabase.table("profiles")
        .update(payload)
        .eq("id", str(profile_id))
        .eq("user_id", str(user_id))
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "Profile not found"}},
        )
    return result.data[0]


async def delete_profile(supabase: Client, user_id: UUID, profile_id: UUID) -> None:
    """Delete a profile, verifying ownership. Cannot delete 'own' profile."""
    # Verify ownership and get profile
    profile = await get_profile(supabase, user_id, profile_id)
    if profile.get("profile_type") == "own":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "bad_request", "message": "Cannot delete your own profile"}},
        )
    result = (
        supabase.table("profiles")
        .delete()
        .eq("id", str(profile_id))
        .eq("user_id", str(user_id))
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "Profile not found"}},
        )


# ---------------------------------------------------------------------------
# Managed-profile lifecycle (caregiver POV)
# ---------------------------------------------------------------------------


async def _fetch_profile_unscoped(supabase: Client, profile_id: UUID) -> dict:
    """Fetch a profile without ownership scoping. Used for caregiver flows
    where the profile belongs to another user but the current user has
    legitimate access via a caregiver_relations row."""
    result = supabase.table("profiles").select("*").eq("id", str(profile_id)).execute()
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "Profile not found"}},
        )
    return result.data[0]


async def disconnect_managed_profile(
    supabase: Client,
    user_id: UUID,
    profile_id: UUID,
) -> dict:
    """Revoke any caregiver_relations linking the current user to the
    profile's owner. Used when the caregiver wants to stop managing the
    profile. Idempotent: if no relation exists, returns the profile."""
    profile = await _fetch_profile_unscoped(supabase, profile_id)
    if profile["user_id"] == str(user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "bad_request",
                    "message": "Cannot disconnect from your own profile; use DELETE",
                }
            },
        )

    rel = (
        supabase.table("caregiver_relations")
        .select("id")
        .eq("patient_user_id", profile["user_id"])
        .eq("caregiver_user_id", str(user_id))
        .in_("status", ["active", "patient_confirmation", "pending"])
        .execute()
    )
    for row in rel.data or []:
        supabase.table("caregiver_relations").update({"status": "revoked"}).eq("id", row["id"]).execute()

    return profile


async def resend_profile_invite(
    supabase: Client,
    user_id: UUID,
    profile_id: UUID,
) -> dict:
    """Regenerate the invite_code on the most recent pending caregiver_relations
    row associated with the profile's owner. The current user must be either
    the patient who issued the invite or the profile owner."""
    from app.services.caregivers_service import (
        INVITE_EXPIRY_HOURS,
        _generate_invite_code,
    )

    profile = await _fetch_profile_unscoped(supabase, profile_id)
    rel = (
        supabase.table("caregiver_relations")
        .select("*")
        .eq("patient_user_id", profile["user_id"])
        .eq("status", "pending")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if not rel.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "No pending invite for this profile"}},
        )
    relation = rel.data[0]
    if str(user_id) not in {relation["patient_user_id"], profile["user_id"]}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "forbidden", "message": "Cannot resend invite for this profile"}},
        )

    new_expires = (datetime.now(timezone.utc) + timedelta(hours=INVITE_EXPIRY_HOURS)).isoformat()
    supabase.table("caregiver_relations").update(
        {
            "invite_code": _generate_invite_code(),
            "invite_expires_at": new_expires,
        }
    ).eq("id", relation["id"]).execute()

    return profile


async def cancel_profile_connection(
    supabase: Client,
    user_id: UUID,
    profile_id: UUID,
) -> None:
    """Cancel a pending connection to a managed profile. Deletes any pending
    caregiver_relations rows and, if the profile was created by the current
    user as a placeholder for the invite, removes the profile too."""
    profile = await _fetch_profile_unscoped(supabase, profile_id)

    pending = (
        supabase.table("caregiver_relations")
        .select("id")
        .eq("patient_user_id", profile["user_id"])
        .eq("status", "pending")
        .execute()
    )
    for row in pending.data or []:
        supabase.table("caregiver_relations").delete().eq("id", row["id"]).execute()

    is_owner = profile["user_id"] == str(user_id)
    is_placeholder = profile.get("profile_type") in {"assisted", "dependent"}
    if is_owner and is_placeholder:
        supabase.table("profiles").delete().eq("id", str(profile_id)).execute()
