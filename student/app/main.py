"""Entrypoint FastAPI — servico student."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.api.authenticated import (
    diplomas_router,
    documents_router,
    exams_router,
    pending_router,
    students_router,
)
from app.api.health import router as health_router
from app.config import get_settings
from app.db import close_db
from app.exceptions import DomainError
from app.metrics import setup_metrics
from app.utils.logging import configure_logging

settings = get_settings()
logger = structlog.get_logger()

_started_at = datetime.now(UTC)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("service.startup", service=settings.service_name)
    yield
    await close_db()
    logger.info("service.shutdown", service=settings.service_name)


configure_logging()

app = FastAPI(title=settings.service_name, version=settings.app_version, lifespan=lifespan)

limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "detail": exc.message},
    )


app.include_router(students_router)
app.include_router(documents_router)
app.include_router(exams_router)
app.include_router(diplomas_router)
app.include_router(pending_router)
app.include_router(health_router)
setup_metrics(app)


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
        "version": settings.app_version,
        "uptime_seconds": int((datetime.now(UTC) - _started_at).total_seconds()),
    }
