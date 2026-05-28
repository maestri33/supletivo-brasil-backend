"""Health/readiness endpoints — coordinator-service."""

from fastapi import APIRouter

from app.schemas.health import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(ok=True)


@router.get("/ready", response_model=HealthResponse)
async def ready() -> HealthResponse:
    return HealthResponse(ok=True)
