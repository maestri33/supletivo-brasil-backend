"""Entrypoint FastAPI — commissions service.

Roda em: uvicorn app.main:app --host 0.0.0.0 --port 8014
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.config import get_settings
from app.db import close_db
from app.metrics import setup_metrics
from app.utils.logging import configure_logging, get_logger
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

settings = get_settings()
configure_logging(level=settings.log_level)
logger = get_logger("commissions")

_started_at = datetime.now(UTC)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("service.startup", service=settings.service_name, env=settings.env)

    # Start worker loop as background asyncio task
    try:
        from app.services.worker import worker_loop

        worker_task = asyncio.create_task(worker_loop())
    except Exception:
        logger.warning("worker.startup_failed", exc_info=True)
        worker_task = None

    yield

    if worker_task:
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass

    await close_db()
    logger.info("service.shutdown", service=settings.service_name)


app = FastAPI(
    title=settings.service_name,
    version=settings.version,
    lifespan=lifespan,
)

# ── Rate limiting (slowapi) ─────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])

# ── SlowAPI middleware ──────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
from slowapi.middleware import SlowAPIMiddleware  # noqa: E402

app.add_middleware(SlowAPIMiddleware)


# ── Error handlers ──────────────────────────────────────────
class _DomainError(Exception):
    """Erro de dominio com status HTTP."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@app.exception_handler(_DomainError)
async def _handle_domain_error(request: Request, exc: _DomainError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


# ── Routers ─────────────────────────────────────────────────
app.include_router(api_router)
setup_metrics(app)


# Re-export DomainError for use in routers/services
import sys  # noqa: E402

if "commissions" not in sys.modules:
    import app as commissions  # noqa: F401

# ── Health / diagnostics ────────────────────────────────────


@app.get("/health")
async def health():
    return {"status": "ok", "service": settings.service_name}


@app.get("/ready")
async def ready():
    return {"status": "ok", "service": settings.service_name}


@app.get("/status")
async def status():
    return {
        "status": "ok",
        "service": settings.service_name,
        "version": settings.version,
        "uptime_seconds": int((datetime.now(UTC) - _started_at).total_seconds()),
    }
