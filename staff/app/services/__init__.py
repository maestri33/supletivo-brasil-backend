"""Servicos do staff — logica de negocio que orquestra chamadas a outros microservicos."""

from __future__ import annotations

import httpx

from app.config import get_settings
from app.schemas import ServiceHealth

settings = get_settings()


async def _check_service(name: str, base_url: str) -> ServiceHealth:
    """Verifica a saude de um servico via /health."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{base_url.rstrip('/')}/health")
            return ServiceHealth(service=name, status="ok", **resp.json())
    except httpx.HTTPError:
        return ServiceHealth(service=name, status="down", detail="unreachable")
    except Exception as exc:
        return ServiceHealth(service=name, status="down", detail=str(exc))


# Servicos a monitorar — chave = nome, valor = URL base.
# Em producao, os URLs vem do docker-compose (nome do container = hostname).
SERVICES_TO_MONITOR: dict[str, str] = {
    "hub": settings.HUB_BASE_URL,
    # Adicionar mais servicos conforme crescer: auth, lead, candidate, etc.
}


async def aggregate_health() -> list[ServiceHealth]:
    """Agrega /health de todos os servicos monitorados."""
    results: list[ServiceHealth] = []
    for name, url in SERVICES_TO_MONITOR.items():
        results.append(await _check_service(name, url))
    return results
