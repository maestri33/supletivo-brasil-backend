"""Client HTTP para o Documents Service (documents.local)."""

from __future__ import annotations

import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class DocumentsClient:
    """Async HTTP client para o Documents Service — provisionamento de documentos."""

    def __init__(self, base_url: str | None = None, timeout: int = 10) -> None:
        self._base = (base_url or get_settings().DOCUMENTS_SERVICE_URL).rstrip("/")
        self._timeout = timeout

    async def __aenter__(self) -> DocumentsClient:
        self._client = httpx.AsyncClient(
            base_url=self._base,
            timeout=self._timeout,
            headers={"Accept": "application/json"},
        )
        return self

    async def __aexit__(self, *args: object) -> None:
        await self._client.aclose()

    # ── Documentos ─────────────────────────────────

    async def ensure(self, external_id: str) -> dict:
        """GET /api/v1/documentos/{external_id} — get-or-create do documento (sub-docs null)."""
        resp = await self._request("GET", f"/api/v1/documentos/{external_id}")
        return resp.json()

    # ── Internal ───────────────────────────────────

    async def _request(self, method: str, path: str) -> httpx.Response:
        logger.debug(f"[documents] {method} {self._base}{path}")
        resp = await self._client.request(method, path)
        logger.debug(f"[documents] ← {resp.status_code}")
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
            raise DocumentsError(resp.status_code, detail)
        return resp


class DocumentsError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        self.status = status
        self.detail = detail
        super().__init__(f"[{status}] {detail}")
