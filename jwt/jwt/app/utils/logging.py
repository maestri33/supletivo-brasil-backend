"""Logging estruturado com structlog + middleware de requisicao."""

import logging
import sys
import time

import structlog
from starlette.middleware.base import BaseHTTPMiddleware


def configure_logging(level: str = "INFO") -> None:
    """Configura structlog uma vez no boot."""
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level.upper())

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper())
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Logger structlog para o modulo chamador."""
    return structlog.get_logger(name)


# ---------------------------------------------------------------------------
# Middleware — loga entrada, saida, duracao e erros de CADA requisicao
# ---------------------------------------------------------------------------

_request_logger = get_logger("http")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Loga o fluxo completo: metodo, path, status, duracao e corpo quando relevante."""

    async def dispatch(self, request, call_next):
        method = request.method
        path = request.url.path

        _request_logger.info("req.in", method=method, path=path)

        start = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = (time.monotonic() - start) * 1000
            _request_logger.error(
                "req.err",
                method=method,
                path=path,
                duration_ms=round(elapsed_ms, 2),
                exc_info=True,
            )
            raise

        elapsed_ms = (time.monotonic() - start) * 1000
        _request_logger.info(
            "req.out",
            method=method,
            path=path,
            status=response.status_code,
            duration_ms=round(elapsed_ms, 2),
        )
        return response
