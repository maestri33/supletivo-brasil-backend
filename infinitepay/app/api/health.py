from fastapi import APIRouter

from app.schemas.health import HealthResponse
from app.services.webhook_security import webhook_security_configured, webhook_security_status

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Health check — retorna ok se o servico estiver respondendo.

    Inclui status da seguranca do webhook para que o dashboard/monitoring
    possa alertar quando o webhook estiver inseguro em producao.
    """
    return HealthResponse(ok=True, webhook_security=webhook_security_status())


@router.get("/ready", response_model=HealthResponse)
async def ready() -> HealthResponse:
    """Readiness probe — retorna ok se o servico estiver pronto para receber trafego.

    Inclui verificacao de webhook security: se nao estiver configurada em
    producao, readiness reporta NOT ok (fail-closed — evita deploy inseguro).
    """
    if not webhook_security_configured():
        return HealthResponse(ok=False)
    return HealthResponse(ok=True)
