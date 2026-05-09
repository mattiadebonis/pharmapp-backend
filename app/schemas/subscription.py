from datetime import datetime
from typing import Literal

from app.schemas.base import PharmaBaseModel

SubscriptionTier = Literal["free", "pro", "family"]
SubscriptionEnvironment = Literal["sandbox", "production"]


class SubscriptionStateDTO(PharmaBaseModel):
    """User entitlement derived from server-validated App Store transactions.
    Populated by store_service.verify_transaction; reset to free when no
    valid transaction exists or the latest one expired."""

    tier: SubscriptionTier = "free"
    is_trial_active: bool = False
    expires_at: datetime | None = None
    last_validated_at: datetime | None = None
    original_transaction_id: str | None = None
    product_id: str | None = None
    environment: SubscriptionEnvironment | None = None


class TransactionVerifyRequest(PharmaBaseModel):
    """JWS signed transaction representation handed to backend by iOS after
    a successful StoreKit purchase or restore."""

    signed_transaction: str
    environment: SubscriptionEnvironment = "production"
