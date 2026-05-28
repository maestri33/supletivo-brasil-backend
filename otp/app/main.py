"""
FastAPI entrypoint.

Run with: uvicorn app.main:app --host 0.0.0.0 --port 8000
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.router import api_router
from app.api.status import router as status_router
from app.config import get_settings
from app.db import close_db
from app.exceptions import DomainError, RateLimitExceeded  # noqa: F811
from app.metrics import setup_metrics
from app.services.cleanup import cleanup_loop
from app.services.queue import queue_loop
from app.utils.logging import configure_logging, get_logger


def _cors_origins() -> list[str]:
    """CORS origins: dev/staging permite *, prod exige CORS_ORIGINS (COD-18 P0.2)."""
    import os as _os

    env = _os.getenv("ENV", _os.getenv("ENVIRONMENT", "development"))
    if env in ("development", "dev", "staging"):
        return ["*"]
    raw = _os.getenv("CORS_ORIGINS", "")
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    return []


settings = get_settings()
configure_logging(settings.log_level, settings.env)
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    log.info("service.startup", service=settings.service_name, env=settings.env)

    stop_event = asyncio.Event()
    http = httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0))
    queue_task = asyncio.create_task(queue_loop(http, stop_event))
    cleanup_task = asyncio.create_task(cleanup_loop(stop_event))

    try:
        yield
    finally:
        stop_event.set()
        await queue_task
        await cleanup_task
        await http.aclose()
        await close_db()
        log.info("service.shutdown")


app = FastAPI(
    title=settings.service_name,
    version="0.2.0",
    lifespan=lifespan,
    description="""
Microsserviço **OTP** — geração e validação de códigos de autenticação descartáveis.

## Funcionalidades

- Gera código OTP numérico e envia via serviço externo **notify**.
- Valida código OTP contra hash SHA256 com TTL configurável.
- Rate limit dedicado por `external_id` (janela curta + janela horária).
- Cleanup automático de logs antigos como task de fundo no lifespan.
- Configuração via variáveis de ambiente (`.env`).
- Logs estruturados em JSON de todas as operações.
- `GET /status` — métricas do serviço (uptime, conexões, latência, falhas).

## Integração

Envia mensagens para o serviço **notify** (`10.10.10.157/api/v1`).
O contacto deve existir previamente no notify.
""",
)

# ── Rate limiting (slowapi) ─────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])

# ── SlowAPI middleware ──────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
from slowapi.middleware import SlowAPIMiddleware  # noqa: E402

app.add_middleware(SlowAPIMiddleware)


# DMZ: CORS origins driven by env. Dev/staging = *, prod = CORS_ORIGINS (COD-18 P0.2).
_origins = _cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=bool(_origins and _origins != ["*"]),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RateLimitExceeded)
async def _handle_rate_limit(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """429 com header Retry-After (segundos)."""
    headers = {}
    if exc.retry_after_s > 0:
        headers["Retry-After"] = str(exc.retry_after_s)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.code,
            "message": exc.message,
            "retry_after_s": exc.retry_after_s,
        },
        headers=headers,
    )


@app.exception_handler(DomainError)
async def _handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
    """Convert domain exceptions to standardized HTTP responses."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message},
    )


app.include_router(status_router)
app.include_router(api_router)
setup_metrics(app)
