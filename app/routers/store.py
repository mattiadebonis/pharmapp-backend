from typing import Any

from fastapi import APIRouter, Body, Depends
from supabase import Client

from app.auth.models import AuthenticatedUser
from app.config import Settings, get_settings
from app.dependencies import get_current_user, get_supabase
from app.schemas.subscription import SubscriptionStateDTO, TransactionVerifyRequest
from app.services.store_service import (
    get_subscription_state,
    process_apple_notification,
    verify_transaction,
)

router = APIRouter(prefix="/store", tags=["Store"])


@router.post("/transactions/verify", response_model=SubscriptionStateDTO)
async def verify_transaction_endpoint(
    data: TransactionVerifyRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
    settings: Settings = Depends(get_settings),
):
    row = await verify_transaction(
        supabase,
        user.user_id,
        data.signed_transaction,
        data.environment,
        settings,
    )
    return row


@router.post("/transactions/notification", status_code=202)
async def apple_notification_endpoint(
    body: dict[str, Any] = Body(...),
    supabase: Client = Depends(get_supabase),
    settings: Settings = Depends(get_settings),
):
    """Apple App Store Server notification v2 webhook. The body contains a
    single ``signedPayload`` JWS; no application authentication. Returns 202
    on accept regardless of whether the transaction was found, to satisfy
    Apple's retry expectations."""
    signed_payload = body.get("signedPayload") or body.get("signed_payload")
    if signed_payload:
        await process_apple_notification(supabase, signed_payload, settings)
    return {"status": "accepted"}


@router.get("/subscription", response_model=SubscriptionStateDTO)
async def get_subscription_endpoint(
    user: AuthenticatedUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    return await get_subscription_state(supabase, user.user_id)
