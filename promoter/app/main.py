"""Entrypoint FastAPI — promoter service.

Roda em: uvicorn app.main:app --host 0.0.0.0 --port 8000
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.config import get_settings
from app.db import close_db
from app.exceptions import DomainError
from app.utils.logging import configure_logging, get_logger
from app.metrics import setup_metrics

settings = get_settings()
configure_logging()
logger = get_logger("promoter")

_started_at = datetime.now(UTC)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("service.startup", service=settings.service_name, env=settings.environment)
    yield
    await close_db()
    logger.info("service.shutdown", service=settings.service_name)


app = FastAPI(
    title=settings.service_name,
    version=settings.app_version,
    lifespan=lifespan,
)


@app.exception_handler(DomainError)
async def _handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
    """Converte excecoes de dominio em respostas HTTP padronizadas."""
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


app.include_router(api_router)
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
        "environment": settings.environment,
        "uptime_seconds": int((datetime.now(UTC) - _started_at).total_seconds()),
    }
