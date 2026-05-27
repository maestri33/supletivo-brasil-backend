"""Client HTTP para o Address Service (address.local)."""

from __future__ import annotations

import httpx

from app.config import get_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class AddressClient:
    """Async HTTP client para o Address Service — provisionamento de endereco."""

    def __init__(self, base_url: str | None = None, timeout: int = 10) -> None:
        self._base = (base_url or get_settings().ADDRESS_SERVICE_URL).rstrip("/")
        self._timeout = timeout

    async def __aenter__(self) -> AddressClient:
        self._client = httpx.AsyncClient(
            base_url=self._base,
            timeout=self._timeout,
            headers={"Accept": "application/json"},
        )
        return self

    async def __aexit__(self, *args: object) -> None:
        await self._client.aclose()

    # ── Enderecos ──────────────────────────────────

    async def ensure(self, external_id: str, entity_type: str = "user") -> dict:
        """GET /api/v1/entities/{entity_type}/{external_id} — get-or-create (null)."""
        resp = await self._request("GET", f"/api/v1/entities/{entity_type}/{external_id}")
        return resp.json()

    # ── Internal ───────────────────────────────────

    async def _request(self, method: str, path: str) -> httpx.Response:
        logger.debug(f"[address] {method} {self._base}{path}")
        resp = await self._client.request(method, path)
        logger.debug(f"[address] ← {resp.status_code}")
        if resp.status_code >= 400:
            detail = f"{method} {path} → {resp.status_code}"
            try:
                body = resp.json()
                if isinstance(body, dict):
                    code = body.get("code", "")
                    msg = body.get("message", body.get("detail", str(body)))
                    detail = f"{code}: {msg}"
            except Exception:
                detail = resp.text or detail
            raise AddressError(resp.status_code, detail)
        return resp


class AddressError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        self.status = status
        self.detail = detail
        super().__init__(f"[{status}] {detail}")
