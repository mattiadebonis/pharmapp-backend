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
    """Create a new profile for the user."""
    payload = data.model_dump(exclude_none=True)
    payload["user_id"] = str(user_id)
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


async def update_profile(supabase: Client, user_id: UUID, profile_id: UUID, data) -> dict:
    """Update a profile, verifying ownership."""
    payload = data.model_dump(exclude_none=True)
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
