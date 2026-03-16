from uuid import UUID

from jose import JWTError, jwt

from app.auth.models import AuthenticatedUser


def decode_access_token(token: str, jwt_secret: str) -> AuthenticatedUser:
    """Decode and verify a Supabase JWT access token."""
    try:
        payload = jwt.decode(
            token,
            jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except JWTError:
        raise
    return AuthenticatedUser(
        user_id=UUID(payload["sub"]),
        email=payload.get("email"),
        role=payload.get("role", "authenticated"),
    )
