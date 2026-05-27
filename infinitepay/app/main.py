"""Entrypoint FastAPI.

Roda em: uvicorn app.main:app --host 0.0.0.0 --port 8000
"""

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.health import router as health_router
from app.api.router import router as api_router
from app.config import get_settings
from app.db import close_db
from app.exceptions import DomainError
from app.utils.logging import configure_logging, log_event
from app.workers import outbound_queue
from app.metrics import setup_metrics
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    log_event("service.startup")
    stop = asyncio.Event()
    worker_task: asyncio.Task | None = None
    if get_settings().run_inline_worker:
        worker_task = asyncio.create_task(outbound_queue.run_worker_loop(stop))
    try:
        yield
    finally:
        stop.set()
        if worker_task is not None:
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass
        log_event("service.shutdown")
        await close_db()


def _cors_origins() -> list[str]:
    """CORS origins: dev/staging permite *, prod exige CORS_ORIGINS (COD-18 P0.2)."""
    env = os.getenv("ENV", os.getenv("ENVIRONMENT", "development"))
    if env in ("development", "dev", "staging"):
        return ["*"]
    raw = os.getenv("CORS_ORIGINS", "")
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    return []


def create_app() -> FastAPI:
    configure_logging()

    tags_metadata = [
        {"name": "health", "description": "Health check e readiness probe."},
        {
            "name": "checkout",
            "description": "Criacao, listagem e consulta de links de pagamento InfinitePay.",
        },
        {
            "name": "webhook",
            "description": "Recebimento de webhooks server-to-server da InfinitePay.",
        },
    ]

    app = FastAPI(
        title="infinitepay API",
        version="1.0.0",
        description="Integracao com a API de checkout da InfinitePay.",
        contact={"name": "InfinitePay Team"},
        license_info={"name": "MIT"},
        openapi_tags=tags_metadata,
        summary="Cria checkouts InfinitePay, recebe webhooks e reenvia eventos internos.",
        lifespan=lifespan,
    )

    # ── Rate limiting (slowapi) ─────────────────────────────────
    limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])

    # ── SlowAPI middleware ──────────────────────────────────────
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    from slowapi.middleware import SlowAPIMiddleware
    app.add_middleware(SlowAPIMiddleware)


    _origins = _cors_origins()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origins,
        allow_credentials=bool(_origins and _origins != ["*"]),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(DomainError)
    async def _domain_err(_req, exc: DomainError):
        return JSONResponse(status_code=exc.code, content={"detail": str(exc), **exc.extra})

    app.include_router(health_router, tags=["health"])
    app.include_router(api_router)
    setup_metrics(app)
    return app


app = create_app()
