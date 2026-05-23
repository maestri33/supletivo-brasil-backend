"""Health checks — /health, /ready, /status no root."""

import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session

router = APIRouter()
settings = get_settings()
_started_at = time.time()
_started_dt = datetime.now(timezone.utc)


def _uptime_seconds() -> float:
    return round(time.time() - _started_at, 2)


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": settings.service_name}


@router.get("/ready")
async def ready(session: AsyncSession = Depends(get_session)) -> dict:
    try:
        await session.execute(text("SELECT 1"))
        return {"status": "ok", "service": settings.service_name}
    except Exception as exc:
        return {"status": "not_ready", "detail": str(exc)}


@router.get("/status")
async def status() -> dict:
    return {
        "status": "ok",
        "service": settings.service_name,
        "version": settings.version,
        "uptime_seconds": int(_uptime_seconds()),
    }
