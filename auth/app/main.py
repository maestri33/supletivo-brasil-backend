"""Entrypoint FastAPI — lifespan, CORS, middleware, exception handler."""

import time
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi_structured_logging import AccessLogConfig, AccessLogMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.router import api_router
from app.config import Environment, get_settings
from app.exceptions import DomainError
from app.metrics import setup_metrics
from app.utils import logging as logs_tool
from app.utils.logging import configure_logging

settings = get_settings()

# ── Structlog config (CONVENTION §2) ──────────────────────────
configure_logging(
    level="DEBUG" if settings.ENVIRONMENT == Environment.DEVELOPMENT else "INFO",
    json_logs=(settings.ENVIRONMENT != Environment.DEVELOPMENT),
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.REDIS_URL:
        try:
            app.state.redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        except Exception:
            app.state.redis = None
    else:
        app.state.redis = None
    yield
    if app.state.redis:
        await app.state.redis.aclose()


app_configs: dict = {
    "title": "Auth Service",
    "version": settings.APP_VERSION,
    "lifespan": lifespan,
}

if settings.ENVIRONMENT not in (Environment.DEVELOPMENT, Environment.STAGING):
    app_configs["openapi_url"] = None

app = FastAPI(**app_configs)

# ── Rate limiting (slowapi) ─────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])

# ── SlowAPI middleware ──────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
from slowapi.middleware import SlowAPIMiddleware  # noqa: E402

app.add_middleware(SlowAPIMiddleware)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=bool(settings.CORS_ORIGINS),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
setup_metrics(app)


# ── Structured access logging ───────────────────────────────

access_config = AccessLogConfig(
    log_level="info",
    exclude_paths={"/health", "/ready", "/api/v1/log"},
    custom_fields={"app_version": settings.APP_VERSION},
)

app.add_middleware(
    AccessLogMiddleware,
    config=access_config,
)

# ── Global exception handler ───────────────────────────────────


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "code": exc.code, **exc.extra},
    )


# ── Redis log storage middleware ───────────────────────────────

SENSITIVE_FIELDS = {
    "otp_code",
    "refresh_token",
    "access_token",
    "password",
    "secret",
    "token",
    "code",
    "key",
    "cpf",
    "phone",
    "email",
}


def _sanitize_body(body: dict | None) -> dict | None:
    if not isinstance(body, dict):
        return body
    return {k: ("***" if k in SENSITIVE_FIELDS else v) for k, v in body.items()}


@app.middleware("http")
async def store_log_in_redis(request: Request, call_next):
    start = time.monotonic()
    body = None
    if request.method in ("POST", "PUT", "PATCH"):
        try:
            body = await request.json()
        except Exception:
            pass

    response = await call_next(request)
    duration_ms = int((time.monotonic() - start) * 1000)

    try:
        if request.url.path != "/api/v1/log":
            redis = getattr(request.app.state, "redis", None)
            await logs_tool.store_log(
                redis,
                direction="in",
                service="auth",
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                request_body=_sanitize_body(body),
                response_body=None,
                duration_ms=duration_ms,
            )
    except Exception:
        pass

    return response


# ── Health / Ready ─────────────────────────────────────────


@app.get("/health")
async def health():
    return {"status": "ok", "version": settings.APP_VERSION}


@app.get("/ready")
async def ready():
    return {"status": "ready"}
