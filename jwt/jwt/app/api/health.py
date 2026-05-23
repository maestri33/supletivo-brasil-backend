"""Endpoints de status — health, readiness e dashboard raiz."""

import os
import sys
import time

from fastapi import APIRouter

from app.config import get_settings
from app.stats import get_stats

router = APIRouter()
_settings = get_settings()


def _fmt_local(ts: float) -> str:
    """Formata timestamp no timezone local do sistema."""
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(ts))


def _memory_mb() -> float:
    try:
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    except Exception:
        return 0.0


@router.get("/")
async def root() -> dict:
    """Dashboard — status completo do servico."""
    stats = get_stats()
    return {
        "service": _settings.service_name,
        "version": "1.0.0",
        "environment": _settings.env,
        "status": "running",
        "uptime_seconds": round(stats.uptime_seconds, 0),
        "started_at": _fmt_local(stats.started_at),
        "server_time": _fmt_local(time.time()),
        "config": {
            "algorithm": _settings.jwt_algorithm,
            "access_expire_min": _settings.jwt_access_expire_minutes,
            "refresh_expire_min": _settings.jwt_refresh_expire_minutes,
            "issuer": _settings.jwt_issuer,
        },
        "stats": {
            "tokens_issued": stats.tokens_issued,
            "tokens_refreshed": stats.tokens_refreshed,
            "jwks_fetches": stats.jwks_fetches,
            "errors": stats.errors,
        },
        "system": {
            "python": sys.version.split()[0],
            "pid": os.getpid(),
            "memory_mb": round(_memory_mb(), 1),
        },
        "endpoints": {
            "health": "/health",
            "ready": "/ready",
            "jwks": "/.well-known/jwks.json",
            "tokens": "/api/v1/tokens",
            "docs": "/docs",
        },
    }


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": _settings.service_name}


@router.get("/ready")
async def ready() -> dict:
    return {"status": "ok", "service": _settings.service_name}


@router.get("/status")
async def status() -> dict:
    """Resumo de runtime — alias enxuto da raiz para a convenção v7m."""
    stats = get_stats()
    return {
        "status": "ok",
        "service": _settings.service_name,
        "version": "1.0.0",
        "environment": _settings.env,
        "uptime_seconds": int(stats.uptime_seconds),
        "tokens_issued": stats.tokens_issued,
        "tokens_refreshed": stats.tokens_refreshed,
    }
