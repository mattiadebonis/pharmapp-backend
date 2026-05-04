"""
DSAR (Data Subject Access Request) endpoints — GDPR art. 15 / 17.

Mounted under `/v2/me/...`. The user_id is always read from the JWT via
`get_current_user`; nothing in this router accepts a user_id from body,
query, or path. That keeps the IDOR surface area at zero.

Rate limits are aggressive on purpose: export and delete are expensive
and inherently sensitive operations; we'd rather force the client to
back off than let a compromised token enumerate or thrash.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from supabase import Client

from app.auth.models import AuthenticatedUser
from app.dependencies import get_current_user, get_supabase
from app.middleware.rate_limit import limiter
from app.schemas.dsar import AccessLogEntry, DeleteAccountResponse, ExportResponse
from app.services.dsar_service import delete_account, export_full_state, list_access_log

router = APIRouter(prefix="/me", tags=["DSAR"])


@router.get("/export", response_model=ExportResponse)
@limiter.limit("3/hour")
async def export_user_data(
    request: Request,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    supabase: Annotated[Client, Depends(get_supabase)],
) -> dict:
    """GDPR art. 15 — return all data we hold on the caller.

    Aggressive 3/hour limit: the export is heavy (joins across ~17 tables
    and pulls full history). A legitimate user almost never needs more
    than one a day; multiple in an hour is either a bug in the client
    or an attacker enumerating.
    """
    return await export_full_state(supabase, user.user_id)


@router.delete(
    "",
    response_model=DeleteAccountResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
@limiter.limit("3/day")
async def delete_my_account(
    request: Request,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    supabase: Annotated[Client, Depends(get_supabase)],
) -> dict:
    """GDPR art. 17 — irreversibly delete the caller's account.

    Cascades to every PHI table via FK on `auth.users(id)`. The iOS
    client should drop its keychain token and clear Core Data the moment
    it sees a 202 — the next request would 401 anyway.
    """
    return await delete_account(supabase, user.user_id)


@router.get("/access-log", response_model=list[AccessLogEntry])
async def my_access_log(
    request: Request,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    supabase: Annotated[Client, Depends(get_supabase)],
    since: Annotated[datetime | None, Query()] = None,
) -> list[dict]:
    """Returns the audit trail filtered to rows where the caller is the
    actor or the target. Used by the iOS Privacy Settings screen to show
    "who accessed what, when" — particularly relevant when caregivers
    are involved.
    """
    return await list_access_log(supabase, user.user_id, since)
