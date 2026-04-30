"""
Rate limiting middleware using slowapi.

IP resolution: reads X-Forwarded-For first (set by Nginx/Fly.io proxy),
falls back to direct client IP. This ensures the real user IP is used
even behind a reverse proxy.

Limits:
- Sensitive endpoints (invite code, auth-adjacent): 10/minute per IP
- General API: 300/minute per IP
- Global hard cap: 1000/hour per IP (catches scrapers/abusers)
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded

from app.config import get_settings


def get_real_ip(request: Request) -> str:
    """
    Extract the real client IP. Honors X-Forwarded-For only when
    `trust_proxy_header` is enabled (deployments behind a known reverse
    proxy such as Nginx/Fly.io); otherwise the header is ignored to
    prevent spoofing by direct clients.
    """
    if get_settings().trust_proxy_header:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


limiter = Limiter(
    key_func=get_real_ip,
    default_limits=["300/minute", "1000/hour"],
)


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={
            "error": {
                "code": "rate_limit_exceeded",
                "message": "Troppe richieste. Riprova tra poco.",
                "retry_after": str(getattr(exc, "retry_after", 60)),
            }
        },
        headers={"Retry-After": str(getattr(exc, "retry_after", 60))},
    )
