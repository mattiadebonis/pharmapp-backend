import base64
import json
import time
from uuid import UUID

import httpx
from jose import JWTError, jwt

from app.auth.models import AuthenticatedUser

# Simple JWKS cache: (jwks_dict, fetched_at)
_jwks_cache: tuple[dict, float] | None = None
_JWKS_TTL = 3600  # refresh every hour


def _get_jwks(supabase_url: str) -> dict:
    """Fetch and cache the JWKS from Supabase (TTL: 1 hour)."""
    global _jwks_cache
    now = time.monotonic()
    if _jwks_cache is None or (now - _jwks_cache[1]) > _JWKS_TTL:
        resp = httpx.get(f"{supabase_url}/auth/v1/.well-known/jwks.json", timeout=10)
        resp.raise_for_status()
        _jwks_cache = (resp.json(), now)
    return _jwks_cache[0]


def _get_jwt_algorithm(token: str) -> str:
    """Extract the algorithm from the JWT header without verifying."""
    header_b64 = token.split(".")[0]
    padding = (4 - len(header_b64) % 4) % 4
    header = json.loads(base64.urlsafe_b64decode(header_b64 + "=" * padding))
    return header.get("alg", "HS256")


def decode_access_token(
    token: str,
    jwt_secret: str,
    supabase_url: str | None = None,
) -> AuthenticatedUser:
    """Decode and verify a Supabase JWT access token.

    Supports both legacy HS256 tokens and new ECC (ES256) tokens issued
    by Supabase after the JWT signing key rotation.
    """
    alg = _get_jwt_algorithm(token)

    if alg in ("ES256", "RS256") and supabase_url:
        jwks = _get_jwks(supabase_url)
        payload = jwt.decode(
            token,
            jwks,
            algorithms=[alg],
            audience="authenticated",
        )
    else:
        payload = jwt.decode(
            token,
            jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )

    return AuthenticatedUser(
        user_id=UUID(payload["sub"]),
        email=payload.get("email"),
        role=payload.get("role", "authenticated"),
    )
