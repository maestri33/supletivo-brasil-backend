"""Entrypoint FastAPI — notify (SQLAlchemy 2)."""

import os
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api.router import api_router
from app.config import get_settings
from app.db import async_session_maker, close_db
from app.exceptions import DomainError
from app.services import metrics_service, template_service
from app.utils.logging import configure_logging, get_logger
from app.metrics import setup_metrics
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address


def _cors_origins() -> list[str]:
    """CORS origins: dev/staging permite *, prod exige CORS_ORIGINS (COD-18 P0.2)."""
    env = os.getenv("ENV", os.getenv("ENVIRONMENT", "development"))
    if env in ("development", "dev", "staging"):
        return ["*"]
    raw = os.getenv("CORS_ORIGINS", "")
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    return []


settings = get_settings()
configure_logging(settings.log_level, json_mode=settings.env != "dev")
log = get_logger(__name__)

_started_at = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    log.info("service.startup", service=settings.service_name, env=settings.env)
    try:
        await template_service.bootstrap_from_disk_if_needed()
    except Exception as exc:  # noqa: BLE001 — bootstrap nao pode bloquear startup
        log.warning("template.bootstrap_failed", error=str(exc))
    try:
        yield
    finally:
        await close_db()
        log.info("service.shutdown")


app = FastAPI(
    title=settings.service_name,
    version="0.5.0",
    lifespan=lifespan,
)

# ── Rate limiting (slowapi) ─────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])

# ── SlowAPI middleware ──────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


_origins = _cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=bool(_origins and _origins != ["*"]),
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Security headers (OWASP A05 — COD-18) ────────────────────
@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(DomainError)
async def _handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message},
    )


# ── Convenção v7m: /health, /ready, /status no root ───────────────────────


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": settings.service_name}


@app.get("/ready")
async def ready() -> dict:
    try:
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ok", "service": settings.service_name, "db": "ok"}
    except Exception:
        return {"status": "not_ready", "db": "unreachable"}


@app.get("/status")
async def status() -> dict:
    """Status + uptime + metricas agregadas (24h por padrao).

    Use `window_hours` query param para outra janela:
      GET /status?window_hours=1
    """
    return {
        "status": "ok",
        "service": settings.service_name,
        "version": app.version,
        "environment": settings.env,
        "uptime_seconds": int(time.time() - _started_at),
        "metrics": await metrics_service.status_snapshot(window_hours=24),
    }


# ── Routers e media ───────────────────────────────────────────────────────


app.include_router(api_router, prefix="/api/v1")
setup_metrics(app)


os.makedirs("media", exist_ok=True)
app.mount("/media", StaticFiles(directory="media"), name="media")
