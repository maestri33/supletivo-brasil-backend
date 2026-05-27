"""Health/readiness endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.schemas.health import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(ok=True)


@router.get("/ready", response_model=HealthResponse)
async def ready(session: AsyncSession = Depends(get_session)) -> HealthResponse:  # noqa: B008
    try:
        await session.execute(text("SELECT 1"))
        return HealthResponse(ok=True)
    except Exception as exc:
        return HealthResponse(ok=False, detail=str(exc))
