"""Apple StoreKit / App Store Server transaction validation.

The iOS client forwards every signed transaction (JWS Compact Serialization)
to POST /v2/store/transactions/verify. The backend decodes the payload,
optionally verifies the signature against Apple's root CA, derives the
entitlement tier from the product_id, and persists the latest state in the
``subscriptions`` table.

When ``settings.apple_verify_signature`` is False (default for dev/test) the
JWS payload is decoded without signature verification — sufficient for unit
tests and local bring-up. In production set ``APPLE_VERIFY_SIGNATURE=true``
and supply ``APPLE_ROOT_CERT_PATH`` to enable cryptographic verification via
``app-store-server-library``.
"""

from __future__ import annotations

import base64
import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from supabase import Client

from app.config import Settings

logger = logging.getLogger("pharmapp.store")


# ---------------------------------------------------------------------------
# JWS decoding
# ---------------------------------------------------------------------------


def _b64url_decode(segment: str) -> bytes:
    padding = 4 - (len(segment) % 4)
    if padding != 4:
        segment += "=" * padding
    return base64.urlsafe_b64decode(segment)


def decode_signed_transaction(signed_transaction: str) -> dict[str, Any]:
    """Return the JWS payload as a dict. Does NOT verify the signature; the
    caller decides whether to perform additional verification.

    Raises HTTPException(400) on malformed input."""
    parts = signed_transaction.split(".")
    if len(parts) != 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "invalid_jws", "message": "Signed transaction must be a JWS"}},
        )
    try:
        payload_bytes = _b64url_decode(parts[1])
        return json.loads(payload_bytes)
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "invalid_jws", "message": "Could not decode signed payload"}},
        ) from exc


def _verify_signature(signed_transaction: str, settings: Settings) -> None:
    """Cryptographic verification via Apple's official library. No-op when
    settings.apple_verify_signature is False."""
    if not settings.apple_verify_signature:
        return
    try:
        # Imported lazily so the dependency is optional in environments that
        # don't ship the Apple library (tests, local dev).
        from appstoreserverlibrary.signed_data_verifier import (  # type: ignore
            SignedDataVerifier,
            VerificationException,
        )
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "verifier_unavailable",
                    "message": "app-store-server-library not installed",
                }
            },
        ) from exc

    if not settings.apple_root_cert_path or not settings.apple_bundle_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "verifier_misconfigured",
                    "message": "APPLE_ROOT_CERT_PATH and APPLE_BUNDLE_ID required when verification enabled",
                }
            },
        )
    try:
        from appstoreserverlibrary.models.Environment import Environment  # type: ignore

        with open(settings.apple_root_cert_path, "rb") as fh:
            root_certs = [fh.read()]
        env_value = (
            Environment.SANDBOX
            if (settings.environment or "").lower() != "production"
            else Environment.PRODUCTION
        )
        verifier = SignedDataVerifier(
            root_certs,
            enable_online_checks=False,
            environment=env_value,
            bundle_id=settings.apple_bundle_id,
        )
        verifier.verify_and_decode_signed_transaction(signed_transaction)
    except VerificationException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "signature_invalid", "message": str(exc)}},
        ) from exc


# ---------------------------------------------------------------------------
# Tier derivation + persistence
# ---------------------------------------------------------------------------


def _tier_for_product(product_id: str | None, settings: Settings) -> str:
    if not product_id:
        return "free"
    return settings.apple_product_tier_map.get(product_id, "free")


def _expires_at_from_payload(payload: dict[str, Any]) -> datetime | None:
    raw = payload.get("expiresDate") or payload.get("expires_date")
    if raw is None:
        return None
    try:
        # Apple returns milliseconds since epoch
        ms = int(raw)
        return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)
    except (TypeError, ValueError):
        return None


def _build_state_row(
    user_id: UUID,
    payload: dict[str, Any],
    settings: Settings,
    environment: str,
) -> dict[str, Any]:
    product_id = payload.get("productId") or payload.get("product_id")
    tier = _tier_for_product(product_id, settings)
    expires_at = _expires_at_from_payload(payload)
    if expires_at is not None and expires_at < datetime.now(timezone.utc):
        # Expired transactions never grant entitlement.
        tier = "free"
    original_tx = payload.get("originalTransactionId") or payload.get("original_transaction_id")
    return {
        "user_id": str(user_id),
        "tier": tier,
        "is_trial_active": bool(payload.get("offerType") == 2),
        "expires_at": expires_at.isoformat() if expires_at else None,
        "last_validated_at": datetime.now(timezone.utc).isoformat(),
        "original_transaction_id": str(original_tx) if original_tx else None,
        "product_id": str(product_id) if product_id else None,
        "environment": environment,
        "raw_payload": payload,
    }


_DTO_FIELDS = {
    "tier",
    "is_trial_active",
    "expires_at",
    "last_validated_at",
    "original_transaction_id",
    "product_id",
    "environment",
}


def _project_dto(row: dict[str, Any]) -> dict[str, Any]:
    """Strip persistence-only fields (``user_id``, ``raw_payload``,
    timestamps) so the response matches ``SubscriptionStateDTO``."""
    return {k: v for k, v in row.items() if k in _DTO_FIELDS}


async def verify_transaction(
    supabase: Client,
    user_id: UUID,
    signed_transaction: str,
    environment: str,
    settings: Settings,
) -> dict[str, Any]:
    """Decode + (optionally) verify a JWS-signed StoreKit transaction and
    upsert the resulting entitlement state."""
    payload = decode_signed_transaction(signed_transaction)
    _verify_signature(signed_transaction, settings)

    bundle_id = payload.get("bundleId") or payload.get("bundle_id")
    if settings.apple_bundle_id and bundle_id and bundle_id != settings.apple_bundle_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "bundle_mismatch", "message": "Bundle id does not match"}},
        )

    row = _build_state_row(user_id, payload, settings, environment)
    supabase.table("subscriptions").upsert(row, on_conflict="user_id").execute()
    return _project_dto(row)


async def get_subscription_state(
    supabase: Client,
    user_id: UUID,
) -> dict[str, Any]:
    """Return the most recent persisted subscription row, or a synthetic
    free-tier row when the user has never validated a transaction."""
    free_tier = {
        "tier": "free",
        "is_trial_active": False,
        "expires_at": None,
        "last_validated_at": None,
        "original_transaction_id": None,
        "product_id": None,
        "environment": None,
    }
    try:
        result = supabase.table("subscriptions").select("*").eq("user_id", str(user_id)).limit(1).execute()
    except Exception as exc:
        # Migration 027 (subscriptions) not yet applied to this Supabase
        # project. Don't block bootstrap — return synthetic free tier so the
        # iOS client can still function. Apply migrations/027_*.sql to fix.
        logger.warning("subscriptions table unavailable, returning free tier: %s", exc)
        return free_tier
    if not result.data:
        return free_tier
    row = result.data[0]
    expires_at = row.get("expires_at")
    # Demote to free if the persisted state is past its expiry. The webhook
    # is supposed to keep this in sync but we double-check on read.
    if expires_at:
        try:
            exp = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
            if exp < datetime.now(timezone.utc):
                row["tier"] = "free"
        except (TypeError, ValueError):
            pass
    return _project_dto(row)


async def process_apple_notification(
    supabase: Client,
    signed_payload: str,
    settings: Settings,
) -> None:
    """Apple S2S notification v2 webhook entry point. Decodes the outer
    notification envelope, then the inner ``signedTransactionInfo`` if
    present, and updates the corresponding subscription row.

    The notification arrives without the user's app-side identity, so we
    locate the subscription by ``original_transaction_id``."""
    notification = decode_signed_transaction(signed_payload)
    _verify_signature(signed_payload, settings)

    data = notification.get("data") or {}
    inner = data.get("signedTransactionInfo")
    if not inner:
        logger.info("Apple notification without signedTransactionInfo: %s", notification.get("notificationType"))
        return
    transaction_payload = decode_signed_transaction(inner)
    original_tx = transaction_payload.get("originalTransactionId") or transaction_payload.get("original_transaction_id")
    if not original_tx:
        return

    existing = (
        supabase.table("subscriptions")
        .select("user_id")
        .eq("original_transaction_id", str(original_tx))
        .limit(1)
        .execute()
    )
    if not existing.data:
        logger.info("Apple notification for unknown original_transaction_id=%s", original_tx)
        return
    user_id = UUID(existing.data[0]["user_id"])

    notif_type = notification.get("notificationType")
    environment = notification.get("data", {}).get("environment", "production").lower()
    row = _build_state_row(user_id, transaction_payload, settings, environment)
    if notif_type in {"REVOKE", "REFUND", "REFUND_REVERSED", "EXPIRED"}:
        row["tier"] = "free"
    supabase.table("subscriptions").upsert(row, on_conflict="user_id").execute()
