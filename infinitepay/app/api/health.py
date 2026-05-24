from fastapi import APIRouter

from app.schemas.health import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Health check — retorna ok se o servico estiver respondendo."""
    return {"ok": True}


@router.get("/ready", response_model=HealthResponse)
async def ready() -> HealthResponse:
    """Readiness probe — retorna ok se o servico estiver pronto para receber trafego."""
    return {"ok": True}
