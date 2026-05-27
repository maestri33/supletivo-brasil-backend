"""Entrypoint FastAPI — enrollment (stub auditivo)."""

import time
from contextlib import asynccontextmanager

import fastapi_structured_logging as fsl
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.enrollments import router as enrollments_router
from app.api.webhooks import router as webhooks_router
from app.api.health import router as health_router
from app.config import get_settings
from app.db import async_session_maker, engine
from app.exceptions import DomainError
from app.metrics import setup_metrics
from app.utils.logging import configure_logging


def _cors_origins() -> list[str]:
    """CORS origins: dev/staging permite *, prod exige CORS_ORIGINS (COD-18 P0.2)."""
    import os as _os
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
    env = _os.getenv("ENV", _os.getenv("ENVIRONMENT", "development"))
    if env in ("development", "dev", "staging"):
        return ["*"]
    raw = _os.getenv("CORS_ORIGINS", "")
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    return []


settings = get_settings()
_started_at = time.time()

fsl.setup_logging(
    json_logs=(settings.env != "dev"),
    log_level=settings.log_level,
)
logger = fsl.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("enrollment_starting", env=settings.env, schema=settings.database_schema)
    yield
    await engine.dispose()
    logger.info("enrollment_stopped")


configure_logging()

app = FastAPI(
    title=settings.service_name,
    version="0.1.0",
    lifespan=lifespan,
)

# ── Rate limiting (slowapi) ─────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])

# ── SlowAPI middleware ──────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
from slowapi.middleware import SlowAPIMiddleware
app.add_middleware(SlowAPIMiddleware)


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhooks_router)
app.include_router(enrollments_router)
app.include_router(health_router)
setup_metrics(app)



@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "code": exc.code},
    )


# ── Structured access logging (porta do local; healthcheck só loga se falhar) ──
access_config = fsl.AccessLogConfig(
    log_level="info",
    exclude_paths_if_ok_or_missing={"/health", "/ready", "/status"},
    custom_fields={"service": settings.service_name, "env": settings.env},
)
app.add_middleware(fsl.AccessLogMiddleware, config=access_config)


@app.get("/health")
async def health():
    return {"status": "ok", "service": settings.service_name}


@app.get("/ready")
async def ready():
    try:
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ok", "service": settings.service_name, "db": "ok"}
    except Exception:
        return {"status": "not_ready", "db": "unreachable"}


@app.get("/status")
async def status():
    return {
        "status": "ok",
        "service": settings.service_name,
        "version": app.version,
        "environment": settings.env,
        "uptime_seconds": int(time.time() - _started_at),
    }
