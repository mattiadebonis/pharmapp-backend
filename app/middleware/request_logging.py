"""
Per-request structured logging.

Emits a single JSON line per request with:
  - request_id (X-Request-Id header, or freshly minted UUID)
  - method
  - path                     (NEVER url — that would leak query params)
  - status
  - duration_ms
  - user_id                  (from `request.state.user_id` if set)
  - ua_family                (`ios-app` / `ios-other` / `other`)

Things deliberately NOT logged:
  - the request body (might contain PHI)
  - the response body (always)
  - the raw User-Agent (long, sometimes carries device fingerprints)
  - the IP address (we have rate limiting bound to it; the log keeps
    only the country derivable from the proxy if needed)

The middleware also stamps `X-Request-Id` onto the response so the
client can echo it back when reporting issues.
"""

from __future__ import annotations

import time
import uuid

import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

# Use the structlog logger directly so kwargs land in the event dict
# (and therefore go through the scrubbing processor). The stdlib bridge
# would drop `extra=` fields silently.
log = structlog.get_logger("pharmapp.access")


def _ua_family(user_agent: str) -> str:
    if not user_agent:
        return "unknown"
    lowered = user_agent.lower()
    if "pharma" in lowered or "ios" in lowered:
        return "ios-app" if "pharma" in lowered else "ios-other"
    return "other"


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            log.exception(
                "request_failed",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                duration_ms=duration_ms,
            )
            raise

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        # `request.state.user_id` is populated by the auth dependency
        # on protected routes. Public routes (health, /docs) leave it
        # unset, so we fall back to None.
        user_id = getattr(request.state, "user_id", None)

        log.info(
            "request_completed",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
            user_id=str(user_id) if user_id else None,
            ua_family=_ua_family(request.headers.get("user-agent", "")),
        )
        response.headers.setdefault("X-Request-Id", request_id)
        return response
