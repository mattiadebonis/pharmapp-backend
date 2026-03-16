from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from supabase import Client

from app.auth.jwt import decode_access_token
from app.auth.models import AuthenticatedUser
from app.config import Settings, get_settings
from app.db.supabase_client import get_supabase_client

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    settings: Settings = Depends(get_settings),
) -> AuthenticatedUser:
    """Extract and validate the authenticated user from the JWT bearer token."""
    try:
        return decode_access_token(credentials.credentials, settings.supabase_jwt_secret)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "unauthorized", "message": "Invalid or expired token"}},
        )


async def get_supabase(
    settings: Settings = Depends(get_settings),
) -> Client:
    """Return the Supabase client with service_role key."""
    return get_supabase_client(settings.supabase_url, settings.supabase_service_role_key)
