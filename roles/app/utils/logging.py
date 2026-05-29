"""Logging estruturado (structlog, JSON) para eventos operacionais."""

from __future__ import annotations

from typing import Any

import structlog


def configure_logging() -> None:
    """Configura structlog para emitir eventos em JSON (ISO UTC + nível)."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        cache_logger_on_first_use=True,
    )


logger = structlog.get_logger("roles")


def log_event(event: str, **fields: Any) -> None:
    """Emite um evento operacional estruturado. Shim retrocompatível."""
    logger.info(event, **fields)
