"""Entrypoint FastAPI — lead service."""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import fastapi_structured_logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi_structured_logging import AccessLogConfig, AccessLogMiddleware

from app.config import settings
from app.db import engine
from app.api.public.auth import router as auth_router
from app.api.demilitarized.webhooks import router as webhooks_router
from app.api.demilitarized.leads import router as leads_crud_router
from app.api.demilitarized.checkouts import router as checkouts_crud_router
from app.api.health import router as health_router
from app.api.authenticated import (
    captured_router,
    waiting_router,
    checkout_router,
    completed_router,
)

fastapi_structured_logging.setup_logging(log_level=settings.LOG_LEVEL)
logger = fastapi_structured_logging.get_logger()

_started_at = datetime.now(timezone.utc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("service.startup", service=settings.SERVICE_NAME, env=settings.ENVIRONMENT)
    yield
    await engine.dispose()
    logger.info("service.shutdown", service=settings.SERVICE_NAME)


app = FastAPI(
    title=settings.SERVICE_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=bool(settings.CORS_ORIGINS),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    AccessLogMiddleware,
    config=AccessLogConfig(
        exclude_paths_if_ok_or_missing={"/health", "/ready", "/status"},
    ),
)

app.include_router(auth_router)
app.include_router(webhooks_router)
app.include_router(leads_crud_router)
app.include_router(checkouts_crud_router)
app.include_router(captured_router)
app.include_router(waiting_router)
app.include_router(checkout_router)
app.include_router(completed_router)
app.include_router(health_router)


# ── Media estatico (QR Codes PIX + imagens) ─────────────────────────────────
# Serve /api/v1/public/media/<...> a partir do volume lead_media. O prefixo
# /api/v1/public/* casa com o matcher do Caddy listener PUBLICO (:8081), entao
# imagens ficam acessiveis via Tailscale Funnel / dominio publico sem precisar
# adicionar rota nova no proxy.
#
# Acesso: aberto publico (qualquer URL conhecida baixa o arquivo). Nao colocar
# nada sensivel aqui — recibos, contratos, etc. devem ir por endpoint signed
# ou JWT-gated em /api/v1/authenticated/*.
_media_dir = Path(settings.MEDIA_DIR)
(_media_dir / "qrcodes").mkdir(parents=True, exist_ok=True)
(_media_dir / "images").mkdir(parents=True, exist_ok=True)
app.mount("/api/v1/public/media", StaticFiles(directory=str(_media_dir)), name="media")


# ── Health endpoints (root, sem prefixo) ────────────────────────────────────


@app.get("/health")
async def health():
    return {"status": "ok", "service": settings.SERVICE_NAME}


@app.get("/ready")
async def ready():
    return {"status": "ok", "service": settings.SERVICE_NAME}


@app.get("/status")
async def status():
    return {"status": "ok", "service": settings.SERVICE_NAME}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.HOST, port=settings.PORT)
