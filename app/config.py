from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    supabase_url: str
    supabase_service_role_key: str
    supabase_jwt_secret: str
    cors_origins: list[str] = []
    # Hostnames the API will accept in the Host header. In production this
    # MUST be an explicit allowlist (no '*'). Used by TrustedHostMiddleware.
    allowed_hosts: list[str] = ["*"]
    environment: str = "development"
    log_level: str = "INFO"
    trust_proxy_header: bool = False
    # Apple StoreKit / App Store Server API. When apple_verify_signature is
    # False (default in dev/test), the store_service decodes the JWS payload
    # without verifying the signature — useful for tests and bring-up. In
    # production set to True and provide apple_root_cert_path.
    apple_bundle_id: str | None = None
    apple_verify_signature: bool = False
    apple_root_cert_path: str | None = None
    # Map StoreKit product IDs to entitlement tiers. Override via env or
    # provide a JSON map in production. Defaults match the staging product
    # IDs used by the iOS PaywallView.
    apple_product_tier_map: dict[str, str] = {
        "com.pharmapp.pro.monthly": "pro",
        "com.pharmapp.pro.yearly": "pro",
        "com.pharmapp.family.monthly": "family",
        "com.pharmapp.family.yearly": "family",
    }

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @model_validator(mode="after")
    def _check_production_cors(self) -> "Settings":
        if self.environment.lower() == "production":
            if not self.cors_origins:
                raise ValueError("CORS_ORIGINS must be set explicitly in production")
            if "*" in self.cors_origins:
                raise ValueError("CORS_ORIGINS must not contain wildcard '*' in production")
        return self

    @model_validator(mode="after")
    def _check_production_allowed_hosts(self) -> "Settings":
        if self.environment.lower() == "production":
            if not self.allowed_hosts:
                raise ValueError("ALLOWED_HOSTS must be set explicitly in production")
            if "*" in self.allowed_hosts:
                raise ValueError("ALLOWED_HOSTS must not contain wildcard '*' in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
