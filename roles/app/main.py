"""Serviço de Roles — motor de regras de transição (regras lidas do `.env`)."""

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import select

from app.api.router import router
from app.config import settings
from app.db import async_session_maker, engine
from app.exceptions import DomainError, NotFound, ValidationError
from app.metrics import setup_metrics
from app.models.user_role import UserRole
from app.services import rule_catalog
from app.utils.logging import configure_logging, logger


def _cors_origins() -> list[str]:
    """CORS origins: dev/staging permite *, prod exige CORS_ORIGINS (COD-18 P0.2)."""
    env = os.getenv("ENV", os.getenv("ENVIRONMENT", "development"))
    if env in ("development", "dev", "staging"):
        return ["*"]
    raw = os.getenv("CORS_ORIGINS", "")
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    return []


started_at = datetime.now(timezone.utc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    c = rule_catalog.counts()
    logger.info(
        f"Roles service started on port {settings.PORT} "
        f"(rules from .env: total={c['total']} add={c['add']} replace={c['replace']} blocking={c['blocking']})"
    )
    yield
    await engine.dispose()


app = FastAPI(
    title="Roles Service",
    description="Motor de regras de transição de roles para o pipeline v7m.",
    version="0.3.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Rate limiting (slowapi) ─────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
from slowapi.middleware import SlowAPIMiddleware
app.add_middleware(SlowAPIMiddleware)

app.include_router(router)
setup_metrics(app)


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError):
    status_map = {NotFound: 404, ValidationError: 422}
    http_status = 400
    for cls, http_code in status_map.items():
        if isinstance(exc, cls):
            http_status = http_code
            break
    return JSONResponse(
        status_code=http_status,
        content={"detail": exc.message, "code": exc.code},
    )


@app.get("/")
async def root():
    rule_counts = rule_catalog.counts()

    async with async_session_maker() as session:
        active = await session.scalars(select(UserRole).where(UserRole.revoked_at.is_(None)))
        active_list = list(active.all())

    total_assignments = len(active_list)
    users_with_roles = len({r.external_id for r in active_list})

    role_distribution: dict[str, int] = {}
    for r in active_list:
        role_distribution[r.role] = role_distribution.get(r.role, 0) + 1

    top_roles = dict(sorted(role_distribution.items(), key=lambda x: x[1], reverse=True)[:10])

    uptime = str(datetime.now(timezone.utc) - started_at).split(".")[0]

    return {
        "service": settings.SERVICE_NAME,
        "version": app.version,
        "uptime": uptime,
        "rules": rule_counts,
        "users": {
            "total_with_roles": users_with_roles,
            "total_active_assignments": total_assignments,
        },
        "roles": top_roles,
    }


@app.get("/health")
async def health():
    return {"status": "ok", "service": settings.SERVICE_NAME}


@app.get("/ready")
async def ready():
    return {"status": "ok", "service": settings.SERVICE_NAME}


@app.get("/status")
async def status():
    return {
        "status": "ok",
        "service": settings.SERVICE_NAME,
        "version": app.version,
        "uptime_seconds": int((datetime.now(timezone.utc) - started_at).total_seconds()),
        "rules": rule_catalog.counts(),
    }


if __name__ == "__main__":
    uvicorn.run(app, host=settings.HOST, port=settings.PORT)
