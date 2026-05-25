"""Debug / observability endpoints. Exposed only when explicitly wired
from main.py. Keep behind /v2/debug so it's obviously non-product."""

import base64
import json
from typing import Any

from fastapi import APIRouter, Depends, Request
from supabase import Client

from app.auth.models import AuthenticatedUser
from app.dependencies import get_current_user, get_supabase

router = APIRouter(prefix="/debug", tags=["Debug"])


def _peek_token_claims(authorization: str | None) -> dict[str, Any]:
    """Best-effort decode of the JWT payload without verification. Used
    only to surface diagnostic claims like ``is_anonymous`` and ``aal`` —
    the request has already been authenticated upstream, so we trust the
    token's signature was checked there."""
    if not authorization:
        return {}
    parts = authorization.split()
    token = parts[1] if len(parts) == 2 else authorization
    segments = token.split(".")
    if len(segments) < 2:
        return {}
    payload_b64 = segments[1]
    padding = (4 - len(payload_b64) % 4) % 4
    try:
        return json.loads(base64.urlsafe_b64decode(payload_b64 + "=" * padding))
    except (ValueError, json.JSONDecodeError):
        return {}


@router.get("/whoami")
async def whoami_endpoint(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Diagnostic snapshot for the current session. Used to verify that
    the JWT ``sub`` claim is stable across iOS app refreshes (rotation
    detection) and that the user's profile + medication row counts match
    what the device thinks it has.

    Returns:
        sub: the JWT subject claim — should remain stable across refreshes
        is_anonymous: true if the token's ``is_anonymous`` claim is set
        role: token role claim
        aud: token audience claim
        profile_ids: profiles owned by this user_id
        medication_count: medications linked to those profiles
    """
    uid = str(user.user_id)
    claims = _peek_token_claims(request.headers.get("authorization"))

    profiles_r = (
        supabase.table("profiles")
        .select("id, created_at, profile_type, display_name")
        .eq("user_id", uid)
        .execute()
    )
    profiles = profiles_r.data or []
    profile_ids = [p["id"] for p in profiles]

    medication_count = 0
    if profile_ids:
        meds_r = (
            supabase.table("medications")
            .select("id", count="exact")
            .in_("profile_id", profile_ids)
            .execute()
        )
        medication_count = meds_r.count or len(meds_r.data or [])

    aud_claim = claims.get("aud")
    aud_str = aud_claim[0] if isinstance(aud_claim, list) and aud_claim else aud_claim

    return {
        "sub": uid,
        "is_anonymous": bool(claims.get("is_anonymous", False)),
        "role": claims.get("role"),
        "aud": aud_str if isinstance(aud_str, str) else None,
        "session_id": claims.get("session_id"),
        "profile_ids": profile_ids,
        "profile_count": len(profiles),
        "medication_count": medication_count,
        "first_profile_created_at": profiles[0]["created_at"] if profiles else None,
    }
