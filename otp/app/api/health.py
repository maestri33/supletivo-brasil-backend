"""Health/readiness endpoints (SQLAlchemy 2)."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": get_settings().service_name}


@router.get("/ready")
async def ready(session: AsyncSession = Depends(get_session)) -> dict:  # noqa: B008
    try:
        await session.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as exc:
        return {"status": "not_ready", "detail": str(exc)}
