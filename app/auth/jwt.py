import base64
import json
import time
from uuid import UUID

import httpx
from jose import JWTError, jwt

from app.auth.models import AuthenticatedUser

ALLOWED_ALGORITHMS = frozenset({"HS256", "ES256", "RS256"})
ASYMMETRIC_ALGORITHMS = frozenset({"ES256", "RS256"})

_jwks_cache: tuple[dict, float] | None = None
_JWKS_TTL = 3600


def _get_jwks(supabase_url: str) -> dict:
    global _jwks_cache
    now = time.monotonic()
    if _jwks_cache is None or (now - _jwks_cache[1]) > _JWKS_TTL:
        resp = httpx.get(f"{supabase_url}/auth/v1/.well-known/jwks.json", timeout=10)
        resp.raise_for_status()
        _jwks_cache = (resp.json(), now)
    return _jwks_cache[0]


def _peek_algorithm(token: str) -> str:
    try:
        header_b64 = token.split(".", 2)[0]
        padding = (4 - len(header_b64) % 4) % 4
        header = json.loads(base64.urlsafe_b64decode(header_b64 + "=" * padding))
    except (ValueError, IndexError, json.JSONDecodeError) as exc:
        raise JWTError("Malformed JWT header") from exc
    alg = header.get("alg")
    if alg not in ALLOWED_ALGORITHMS:
        raise JWTError(f"Unsupported JWT algorithm: {alg!r}")
    return alg


def decode_access_token(
    token: str,
    jwt_secret: str,
    supabase_url: str | None = None,
) -> AuthenticatedUser:
    """Decode and verify a Supabase JWT access token.

    HS256 path uses the shared secret. ES256/RS256 path uses Supabase JWKS.
    Algorithm is whitelisted before any verification to prevent key/alg confusion.
    """
    alg = _peek_algorithm(token)

    if alg in ASYMMETRIC_ALGORITHMS:
        if not supabase_url:
            raise JWTError("supabase_url required to verify asymmetric JWT")
        payload = jwt.decode(
            token,
            _get_jwks(supabase_url),
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
