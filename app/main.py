import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routers import (
    adherence,
    bootstrap,
    cabinets,
    catalog,
    custom_filters,
    doctors,
    dose_events,
    entries,
    health,
    logs,
    medicines,
    monitoring,
    operations,
    people,
    settings,
    stocks,
    therapies,
)

logger = logging.getLogger("pharmapp")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app_settings = get_settings()
    logging.basicConfig(level=getattr(logging, app_settings.log_level.upper(), logging.INFO))
    logger.info("PharmaApp backend starting (env=%s)", app_settings.environment)
    yield
    logger.info("PharmaApp backend shutting down")


def create_app() -> FastAPI:
    app_settings = get_settings()

    app = FastAPI(
        title="PharmaApp API",
        version="0.1.0",
        lifespan=lifespan,
    )

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

    # Routers
    app.include_router(health.router)
    app.include_router(bootstrap.router, prefix="/v1")
    app.include_router(catalog.router, prefix="/v1")
    app.include_router(settings.router, prefix="/v1")
    app.include_router(people.router, prefix="/v1")
    app.include_router(doctors.router, prefix="/v1")
    app.include_router(cabinets.router, prefix="/v1")
    app.include_router(custom_filters.router, prefix="/v1")
    app.include_router(medicines.router, prefix="/v1")
    app.include_router(entries.router, prefix="/v1")
    app.include_router(therapies.router, prefix="/v1")
    app.include_router(operations.router, prefix="/v1")
    app.include_router(stocks.router, prefix="/v1")
    app.include_router(logs.router, prefix="/v1")
    app.include_router(dose_events.router, prefix="/v1")
    app.include_router(monitoring.router, prefix="/v1")
    app.include_router(adherence.router, prefix="/v1")

    return app


app = create_app()
