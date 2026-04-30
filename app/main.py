import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.middleware import SlowAPIMiddleware
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.middleware.rate_limit import limiter, rate_limit_exceeded_handler
from app.routers import (
    activity_logs,
    bootstrap,
    caregivers,
    catalog,
    device_tokens,
    doctors,
    dose_events,
    dosing_schedules,
    health,
    medications,
    prescription_requests,
    prescriptions,
    profiles,
    routines,
    settings,
    supplies,
)

logger = logging.getLogger("pharmapp")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app_settings = get_settings()
    logging.basicConfig(level=getattr(logging, app_settings.log_level.upper(), logging.INFO))
    logger.info("Pharma Reminder backend starting (env=%s)", app_settings.environment)
    yield
    logger.info("Pharma Reminder backend shutting down")


def create_app() -> FastAPI:
    app_settings = get_settings()

    app = FastAPI(
        title="Pharma Reminder API",
        version="2.0.0",
        lifespan=lifespan,
    )

    # Rate limiting state and middleware
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handlers
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Request validation failed",
                    "details": exc.errors(),
                }
            },
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
    app.include_router(settings.router, prefix="/v2")
    app.include_router(caregivers.router, prefix="/v2")
    app.include_router(activity_logs.router, prefix="/v2")
    app.include_router(device_tokens.router, prefix="/v2")

    return app


app = create_app()
