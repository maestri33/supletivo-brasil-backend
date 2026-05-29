"""Cliente HTTP para o servico hub — cria/le hubs e atribui coordenador.

Usado pelos endpoints desmilitarizados do staff para delegar operacoes de
dominio ao servico dono (hub). Timeout e URL base via Settings.
"""

from uuid import UUID

import httpx
from fastapi import HTTPException

from app.config import get_settings

settings = get_settings()


class HubClient:
    """Cliente HTTP para o servico hub (comunicacao interna via httpx)."""

    def __init__(self) -> None:
        self._base = settings.HUB_BASE_URL.rstrip("/")

    async def _request(self, method: str, path: str, json: dict | None = None) -> dict:
        """Faz request ao hub e trata erros."""
        url = f"{self._base}/api/v1{path}"
        try:
            async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT) as client:
                resp = await client.request(method, url, json=json)
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.json().get("detail", str(exc))
            raise HTTPException(exc.response.status_code, detail) from exc
        except httpx.RequestError as exc:
            raise HTTPException(502, f"hub unreachable: {exc}") from exc

    async def list_hubs(self) -> list[dict]:
        """Lista todos os polos (chamada desmilitarizada ao hub)."""
        data = await self._request("GET", "/hubs")
        return data if isinstance(data, list) else data.get("hubs", [])

    async def get_hub(self, hub_id: UUID) -> dict:
        """Busca um polo por external_id."""
        return await self._request("GET", f"/hubs/{hub_id}")

    async def create_hub(self, name: str, brand: str) -> dict:
        """Cria um polo (chama endpoint autenticado do hub)."""
        return await self._request("POST", "/hubs", {"name": name, "brand": brand})

    async def set_coordinator(self, hub_id: UUID, coordinator_external_id: UUID) -> dict:
        """Define o coordenador de um polo."""
        return await self._request(
            "PUT",
            f"/hubs/{hub_id}/coordinator",
            {"coordinator_external_id": str(coordinator_external_id)},
        )

    async def health(self) -> dict:
        """Verifica saude do hub."""
        return await self._request("GET", "/health")  # na verdade e' /health, nao /api/v1
