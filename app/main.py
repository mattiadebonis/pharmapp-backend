import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings
from app.middleware.rate_limit import limiter, rate_limit_exceeded_handler
from app.middleware.request_logging import RequestLoggingMiddleware
from app.routers import (
    activity_logs,
    bootstrap,
    caregivers,
    catalog,
    device_tokens,
    doctors,
    dose_events,
    dosing_schedules,
    dsar,
    health,
    measurements,
    medications,
    parameters,
    prescription_requests,
    prescriptions,
    profiles,
    routine_steps,
    routines,
    settings,
    supplies,
)

logger = logging.getLogger("pharmapp")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, enable_hsts: bool):
        super().__init__(app)
        self.enable_hsts = enable_hsts

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'none'; frame-ancestors 'none'",
        )
        if self.enable_hsts:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    app_settings = get_settings()
    # structlog + scrubbing processor. Replaces the stdlib basicConfig
    # so PII never reaches stdout in production logs.
    from app.logging_config import setup_logging

    setup_logging(level=app_settings.log_level)
    logger.info("Pharma Reminder backend starting (env=%s)", app_settings.environment)
    yield
    logger.info("Pharma Reminder backend shutting down")


def create_app() -> FastAPI:
    app_settings = get_settings()

    is_production = app_settings.environment.lower() == "production"

    app = FastAPI(
        title="Pharma Reminder API",
        version="2.0.0",
        lifespan=lifespan,
        # In production, hide all OpenAPI / docs endpoints to reduce
        # surface area and avoid leaking schema information.
        docs_url=None if is_production else "/docs",
        redoc_url=None,
        openapi_url=None if is_production else "/openapi.json",
    )

    # Rate limiting state and middleware
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    app.add_middleware(SecurityHeadersMiddleware, enable_hsts=is_production)

    # Per-request structured logging — must come AFTER auth-bearing
    # middlewares so `request.state.user_id` is populated. Starlette's
    # add_middleware adds at the BOTTOM of the chain (i.e. closest to
    # the route), and middlewares execute in reverse insertion order.
    # We add this last so it's the outermost wrapper that sees timing
    # for the entire request.
    app.add_middleware(RequestLoggingMiddleware)

    # Reject requests with Host headers outside the configured allowlist.
    # In dev allowed_hosts defaults to ["*"]; in production the config
    # validator forbids wildcards, so this is always a concrete list.
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=app_settings.allowed_hosts,
    )

    cors_allow_credentials = bool(app_settings.cors_origins) and "*" not in app_settings.cors_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        allow_credentials=cors_allow_credentials,
        # Only the verbs we actually use. PUT and OPTIONS are not part of
        # the v2 surface; OPTIONS is handled by the framework regardless.
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
        max_age=600,
    )

    # Exception handlers
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        payload: dict = {
            "code": "validation_error",
            "message": "Request validation failed",
        }
        if not is_production:
            payload["details"] = exc.errors()
        else:
            # In production, never log raw exc.errors(): each entry contains
            # the `input` field with the user-supplied value, which may be PHI
            # (medication name, free-text note, etc.). Log only metadata.
            scrubbed_errors = [
                {
                    "loc": list(err.get("loc", [])),
                    "type": err.get("type"),
                }
                for err in exc.errors()
            ]
            logger.warning(
                "validation_error path=%s error_count=%d errors=%s",
                request.url.path,
                len(scrubbed_errors),
                scrubbed_errors,
            )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": payload},
        )

    # Routers — v2 (Pharma Reminder)
    app.include_router(health.router)
    app.include_router(bootstrap.router, prefix="/v2")
    app.include_router(catalog.router, prefix="/v2")
    app.include_router(profiles.router, prefix="/v2")
    app.include_router(doctors.router, prefix="/v2")
    app.include_router(medications.router, prefix="/v2")
    app.include_router(dosing_schedules.router, prefix="/v2")
    app.include_router(supplies.router, prefix="/v2")
    app.include_router(prescriptions.router, prefix="/v2")
    app.include_router(prescription_requests.router, prefix="/v2")
    app.include_router(dose_events.router, prefix="/v2")
    app.include_router(routines.router, prefix="/v2")
    app.include_router(routine_steps.router, prefix="/v2")
    app.include_router(parameters.router, prefix="/v2")
    app.include_router(measurements.router, prefix="/v2")
    app.include_router(settings.router, prefix="/v2")
    app.include_router(caregivers.router, prefix="/v2")
    app.include_router(activity_logs.router, prefix="/v2")
    app.include_router(device_tokens.router, prefix="/v2")
    # DSAR (GDPR art. 15/17): export, delete, access-log under /v2/me/...
    app.include_router(dsar.router, prefix="/v2")

    return app


app = create_app()
