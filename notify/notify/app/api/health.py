"""Endpoints de health/readiness/status (SQLAlchemy 2)."""

import time

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session

router = APIRouter()
_started_at = time.time()


@router.get("/health", summary="Liveness probe")
async def health() -> dict:
    return {"status": "ok", "service": get_settings().service_name}


@router.get("/ready", summary="Readiness probe")
async def ready(session: AsyncSession = Depends(get_session)) -> dict:
    try:
        await session.execute(text("SELECT 1"))
        return {"status": "ok", "service": get_settings().service_name, "db": "ok"}
    except Exception:
        return {"status": "not_ready", "db": "unreachable"}


@router.get("/status", summary="Status com uptime")
async def status() -> dict:
    s = get_settings()
    return {
        "status": "ok",
        "service": s.service_name,
        "version": "0.5.0",
        "environment": s.env,
        "uptime_seconds": int(time.time() - _started_at),
    }
