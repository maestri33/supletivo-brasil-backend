"""Client HTTP para o Roles Service (roles.local)."""

from __future__ import annotations

import httpx

from app.config import get_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


def _sanitize_log_body(body: dict | None, sensitive: set[str]) -> dict | None:
    """Remove sensitive fields from log output."""
    if not isinstance(body, dict):
        return body
    return {k: ("***" if k in sensitive else v) for k, v in body.items()}


class RolesClient:
    """Async HTTP client para o Roles Service — motor de regras RBAC."""

    def __init__(self, base_url: str | None = None, timeout: int = 10) -> None:
        self._base = (base_url or get_settings().ROLES_SERVICE_URL).rstrip("/")
        self._timeout = timeout

    async def __aenter__(self) -> RolesClient:
        self._session = httpx.AsyncClient(headers={"Accept": "application/json"})
        return self

    async def __aexit__(self, *args: object) -> None:
        await self._session.aclose()

    # ── Role ───────────────────────────────────────

    async def get_roles(self, external_id: str) -> dict:
        """GET /api/v1/role/{external_id} — roles ativas do usuario."""
        resp = await self._request("GET", f"/api/v1/role/{external_id}")
        return resp.json()

    async def is_blocked(self, external_id: str) -> dict:
        """GET /api/v1/role/{external_id}/blocked — verifica se usuario esta bloqueado."""
        resp = await self._request("GET", f"/api/v1/role/{external_id}/blocked")
        return resp.json()

    async def assign(self, external_id: str, role: str) -> dict:
        """POST /api/v1/role/{external_id}/{role} — atribui role ao usuario."""
        resp = await self._request("POST", f"/api/v1/role/{external_id}/{role}")
        return resp.json()

    async def promote(self, external_id: str, to_role: str) -> dict:
        """POST /api/v1/role/{external_id}/up/{to_role} — promove usuario para nova role."""
        resp = await self._request("POST", f"/api/v1/role/{external_id}/up/{to_role}")
        return resp.json()

    # ── Config ─────────────────────────────────────

    async def get_rule(self, rule_id: str) -> dict:
        """GET /api/v1/config/roles/{rule_id} — busca regra por ID."""
        resp = await self._request("GET", f"/api/v1/config/roles/{rule_id}")
        return resp.json()

    # ── Internal ───────────────────────────────────

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        params: dict | None = None,
    ) -> httpx.Response:
        url = f"{self._base}{path}"
        safe = _sanitize_log_body(json, set())
        logger.debug(f"[roles] {method} {url}" + (f" body={safe}" if safe else ""))
        resp = await self._session.request(
            method,
            url,
            json=json,
            params=params,
            timeout=self._timeout,
        )
        logger.debug(f"[roles] ← {resp.status_code}")
        if resp.status_code >= 400:
            detail = f"{method} {path} → {resp.status_code}"
            try:
                body = resp.json()
                if isinstance(body, dict):
                    detail = (
                        f"{body.get('code', '')}: "
                        f"{body.get('message', body.get('detail', str(body)))}"
                    )
            except Exception:
                detail = resp.text or detail
            raise RolesError(resp.status_code, detail)
        return resp


class RolesError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        self.status = status
        self.detail = detail
        super().__init__(f"[{status}] {detail}")
