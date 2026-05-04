"""
structlog configuration for the FastAPI backend.

Two output paths:
  - stdlib loggers (e.g. `logging.getLogger("pharmapp")`) are
    intercepted by `ProcessorFormatter` so existing call sites keep
    working without rewrites.
  - structlog loggers via `structlog.get_logger(...)` go through the
    same processor chain.

The scrubbing processor is mounted right before the renderer so it has
the last word on every emitted record.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

from app.logging_scrubbing import ScrubbingProcessor


def setup_logging(level: str = "INFO") -> None:
    """Initialise structlog + stdlib logging.

    Idempotent: safe to call from FastAPI lifespan + from tests.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        timestamper,
        ScrubbingProcessor(),  # last before renderer
    ]

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    # Replace any handlers that might have been added by basicConfig
    # in earlier app boots / test runs.
    root.handlers = [handler]
    root.setLevel(log_level)

    # Quiet down a couple of well-known noisy 3rd-party loggers; the
    # scrubber still applies, but keeping log volume sane is its own win.
    for name in ("httpx", "httpcore", "uvicorn.access"):
        logging.getLogger(name).setLevel(max(log_level, logging.WARNING))
