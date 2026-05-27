"""Logging estruturado (structlog, JSON) para eventos operacionais."""

from __future__ import annotations

import structlog


def configure_logging() -> None:
    """Configura structlog para emitir eventos em JSON (ISO UTC + nivel)."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Retorna um logger structlog (nomeado quando informado)."""
    return structlog.get_logger(name or "training")
