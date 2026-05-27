"""Entrypoint FastAPI — hub (polo).

Milestone 1: só a spine (saúde + handler de erro). Rotas de negócio
(read desmilitarizado, write autenticado) entram nos próximos milestones.
"""

import time
from contextlib import asynccontextmanager

import fastapi_structured_logging as fsl
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.hubs import router as hubs_router
from app.config import get_settings
from app.db import async_session_maker, engine
from app.exceptions import DomainError

settings = get_settings()
_started_at = time.time()

fsl.setup_logging(
    json_logs=(settings.env != "dev"),
    log_level=settings.log_level,
)
logger = fsl.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("hub_starting", env=settings.env, schema=settings.database_schema)
    yield
    await engine.dispose()
    logger.info("hub_stopped")


app = FastAPI(
    title=settings.service_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(hubs_router)


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "code": exc.code},
    )


# ── Structured access logging (healthcheck só loga se falhar) ──
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
