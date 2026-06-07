"""Apple StoreKit transaction validation — production-shaped tests.

Covers:
- JWS payload decoding (bundle id check, expiry → free tier demotion)
- Webhook S2S notification flow
- Anti-replay (same originalTransactionId twice → upserts, no duplicate row)
- Tier-mapping for product IDs + unknown product → free
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.config import Settings
from app.services.store_service import (
    decode_signed_transaction,
    get_subscription_state,
    process_apple_notification,
    verify_transaction,
)
from app.tests.conftest import TEST_USER_ID, FakeSupabase


def _make_settings(**overrides) -> Settings:
    defaults = dict(
        supabase_url="http://localhost",
        supabase_service_role_key="test",
        supabase_jwt_secret="test-secret",
        apple_bundle_id="com.pharmapp.ios",
        apple_verify_signature=False,
    )
    defaults.update(overrides)
    return Settings(**defaults)


def _jws(payload: dict) -> str:
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    return f"header.{encoded}.sig"


def _now_ms(offset_seconds: int = 0) -> int:
    return int((datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)).timestamp() * 1000)


# ---------------------------------------------------------------------------
# Pure decode
# ---------------------------------------------------------------------------


class TestDecodeJWS:
    def test_decodes_round_trip(self):
        payload = {"productId": "x", "originalTransactionId": "y"}
        decoded = decode_signed_transaction(_jws(payload))
        assert decoded == payload

    def test_rejects_two_part_jws(self):
        with pytest.raises(HTTPException) as exc:
            decode_signed_transaction("only.two")
        assert exc.value.status_code == 400

    def test_rejects_garbage_payload(self):
        with pytest.raises(HTTPException):
            decode_signed_transaction("h.not!base64.s")


# ---------------------------------------------------------------------------
# Verify transaction
# ---------------------------------------------------------------------------


class TestVerifyTransaction:
    @pytest.mark.asyncio
    async def test_active_pro_yearly_grants_pro_tier(self, fake_supabase: FakeSupabase):
        token = _jws(
            {
                "bundleId": "com.pharmapp.ios",
                "productId": "com.pharmapp.pro.yearly",
                "originalTransactionId": "txn-pro-1",
                "expiresDate": _now_ms(86_400),
            }
        )
        result = await verify_transaction(
            fake_supabase, TEST_USER_ID, token, "production", _make_settings()
        )
        assert result["tier"] == "pro"
        assert result["product_id"] == "com.pharmapp.pro.yearly"
        # Ensure the row was upserted
        upserts = [c for c in fake_supabase.calls if c._table == "subscriptions" and c._operation == "upsert"]
        assert len(upserts) == 1

    @pytest.mark.asyncio
    async def test_expired_transaction_demotes_to_free(self, fake_supabase: FakeSupabase):
        token = _jws(
            {
                "bundleId": "com.pharmapp.ios",
                "productId": "com.pharmapp.pro.yearly",
                "originalTransactionId": "txn-pro-2",
                "expiresDate": _now_ms(-86_400),  # 1 day in the past
            }
        )
        result = await verify_transaction(
            fake_supabase, TEST_USER_ID, token, "production", _make_settings()
        )
        assert result["tier"] == "free"

    @pytest.mark.asyncio
    async def test_bundle_mismatch_400(self, fake_supabase: FakeSupabase):
        token = _jws(
            {
                "bundleId": "com.attacker.app",
                "productId": "com.pharmapp.pro.yearly",
                "originalTransactionId": "txn-3",
                "expiresDate": _now_ms(86_400),
            }
        )
        with pytest.raises(HTTPException) as exc:
            await verify_transaction(
                fake_supabase, TEST_USER_ID, token, "production", _make_settings()
            )
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_unknown_product_id_falls_back_to_free(self, fake_supabase: FakeSupabase):
        token = _jws(
            {
                "bundleId": "com.pharmapp.ios",
                "productId": "com.pharmapp.gold.lifetime",  # unmapped
                "originalTransactionId": "txn-4",
                "expiresDate": _now_ms(86_400),
            }
        )
        result = await verify_transaction(
            fake_supabase, TEST_USER_ID, token, "production", _make_settings()
        )
        assert result["tier"] == "free"

    @pytest.mark.asyncio
    async def test_anti_replay_uses_upsert_not_insert(self, fake_supabase: FakeSupabase):
        """Replaying the same transaction must overwrite the existing row,
        not create a duplicate. The service uses upsert(on_conflict=user_id);
        this test confirms the contract."""
        token = _jws(
            {
                "bundleId": "com.pharmapp.ios",
                "productId": "com.pharmapp.pro.yearly",
                "originalTransactionId": "txn-replay",
                "expiresDate": _now_ms(86_400),
            }
        )
        for _ in range(3):
            await verify_transaction(
                fake_supabase, TEST_USER_ID, token, "production", _make_settings()
            )
        upserts = [c for c in fake_supabase.calls if c._table == "subscriptions" and c._operation == "upsert"]
        assert len(upserts) == 3
        for call in upserts:
            assert call._on_conflict == "user_id"


# ---------------------------------------------------------------------------
# Webhook
# ---------------------------------------------------------------------------


class TestNotificationWebhook:
    @pytest.mark.asyncio
    async def test_revoke_demotes_to_free(self, fake_supabase: FakeSupabase):
        # First seed an active subscription for the user
        fake_supabase.seed_select(
            "subscriptions",
            [{"user_id": str(TEST_USER_ID)}],
        )
        inner = _jws(
            {
                "bundleId": "com.pharmapp.ios",
                "productId": "com.pharmapp.pro.yearly",
                "originalTransactionId": "txn-revoked",
                "expiresDate": _now_ms(86_400),
            }
        )
        outer = _jws(
            {
                "notificationType": "REVOKE",
                "data": {"signedTransactionInfo": inner, "environment": "production"},
            }
        )
        await process_apple_notification(fake_supabase, outer, _make_settings())
        # The notification handler looks up by original_transaction_id; our
        # fake doesn't filter — it returns whatever we seeded. The upsert
        # call should have demoted the tier to free.
        upserts = [c for c in fake_supabase.calls if c._table == "subscriptions" and c._operation == "upsert"]
        assert upserts, "webhook should upsert"
        assert upserts[-1]._payload["tier"] == "free"

    @pytest.mark.asyncio
    async def test_notification_without_inner_is_noop(self, fake_supabase: FakeSupabase):
        outer = _jws({"notificationType": "TEST", "data": {}})
        await process_apple_notification(fake_supabase, outer, _make_settings())
        upserts = [c for c in fake_supabase.calls if c._table == "subscriptions" and c._operation == "upsert"]
        assert not upserts


# ---------------------------------------------------------------------------
# get_subscription_state
# ---------------------------------------------------------------------------


class TestGetSubscriptionState:
    @pytest.mark.asyncio
    async def test_no_row_returns_synthetic_free(self, fake_supabase: FakeSupabase):
        fake_supabase.seed_select("subscriptions", [])
        state = await get_subscription_state(fake_supabase, TEST_USER_ID)
        assert state["tier"] == "free"
        assert state["expires_at"] is None

    @pytest.mark.asyncio
    async def test_expired_row_demotes_on_read(self, fake_supabase: FakeSupabase):
        fake_supabase.seed_select(
            "subscriptions",
            [
                {
                    "user_id": str(TEST_USER_ID),
                    "tier": "pro",
                    "is_trial_active": False,
                    "expires_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
                    "last_validated_at": (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),
                    "original_transaction_id": "txn-expired",
                    "product_id": "com.pharmapp.pro.yearly",
                    "environment": "production",
                }
            ],
        )
        state = await get_subscription_state(fake_supabase, TEST_USER_ID)
        assert state["tier"] == "free"

    @pytest.mark.asyncio
    async def test_active_row_passes_through(self, fake_supabase: FakeSupabase):
        future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        fake_supabase.seed_select(
            "subscriptions",
            [
                {
                    "user_id": str(TEST_USER_ID),
                    "tier": "family",
                    "is_trial_active": False,
                    "expires_at": future,
                    "last_validated_at": datetime.now(timezone.utc).isoformat(),
                    "original_transaction_id": "txn-fam",
                    "product_id": "com.pharmapp.family.yearly",
                    "environment": "production",
                }
            ],
        )
        state = await get_subscription_state(fake_supabase, TEST_USER_ID)
        assert state["tier"] == "family"
