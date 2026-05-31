"""Endpoint de agregacao de health — verifica /health de todos os servicos."""

from fastapi import APIRouter, Depends

from app.dependencies import get_current_external_id
from app.schemas import HealthAggregateResponse
from app.services import aggregate_health

router = APIRouter(tags=["health"])


@router.get(
    "/health/aggregate",
    response_model=HealthAggregateResponse,
    summary="Health aggregation de todos os servicos",
)
async def health_aggregate(
    _external_id=Depends(get_current_external_id),
) -> HealthAggregateResponse:
    """Agrega /health de todos os servicos monitorados. Requer token staff."""
    services = await aggregate_health()
    all_ok = all(s.status == "ok" for s in services)
    return HealthAggregateResponse(services=services, all_ok=all_ok)
