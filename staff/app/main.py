"""Entrypoint FastAPI — staff (boss da operacao).

Milestone 1: spine + auth gate. /health, /ready, /status + endpoint de prova
autenticado. Modelos de dominio (hub/coordenador) entram nos milestones 4/5.
"""

import time
from contextlib import asynccontextmanager

import fastapi_structured_logging as fsl
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api import authenticated_router
from app.config import get_settings
from app.db import async_session_maker, engine
from app.exceptions import DomainError
from app.metrics import setup_metrics
from app.utils.logging import configure_logging

settings = get_settings()
_started_at = time.time()

fsl.setup_logging(
    json_logs=(settings.ENVIRONMENT != "development"),
    log_level=settings.LOG_LEVEL,
)
logger = fsl.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("staff_starting", env=settings.ENVIRONMENT, schema=settings.DATABASE_SCHEMA)
    yield
    await engine.dispose()
    logger.info("staff_stopped")


configure_logging()

app = FastAPI(
    title=settings.SERVICE_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "code": exc.code},
    )


# ── Structured access logging (healthcheck so loga se falhar) ──
access_config = fsl.AccessLogConfig(
    log_level="info",
    exclude_paths_if_ok_or_missing={"/health", "/ready", "/status"},
    custom_fields={"service": settings.SERVICE_NAME, "env": settings.ENVIRONMENT},
)
app.add_middleware(fsl.AccessLogMiddleware, config=access_config)

# ── Routers ────────────────────────────────────────────────────
app.include_router(authenticated_router, prefix="/api/v1")
setup_metrics(app)



# ── Health endpoints ───────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "service": settings.SERVICE_NAME}


@app.get("/ready")
async def ready():
    try:
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ok", "service": settings.SERVICE_NAME, "db": "ok"}
    except Exception:
        return {"status": "not_ready", "db": "unreachable"}


@app.get("/status")
async def status():
    return {
        "status": "ok",
        "service": settings.SERVICE_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "uptime_seconds": int(time.time() - _started_at),
    }
