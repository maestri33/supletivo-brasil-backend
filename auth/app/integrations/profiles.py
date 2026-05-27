"""Client HTTP para o Profiles Service (profiles.local)."""

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


def _redact_cpf_from_url(url: str) -> str:
    """Replace CPF (11 digits) in URL paths with '***'."""
    import re
    return re.sub(r"/cpf/\d{11}", "/cpf/***", url)


class ProfilesClient:
    """Async HTTP client para o Profiles Service — profiles e CPF."""

    def __init__(self, base_url: str | None = None, timeout: int = 10) -> None:
        self._base = (base_url or get_settings().PROFILES_SERVICE_URL).rstrip("/")
        self._timeout = timeout

    async def __aenter__(self) -> ProfilesClient:
        self._session = httpx.AsyncClient(headers={"Accept": "application/json"})
        return self

    async def __aexit__(self, *args: object) -> None:
        await self._session.aclose()

    # ── Profiles ───────────────────────────────────

    async def create(self, external_id: str, cpf: str) -> dict:
        """POST /api/v1/profiles — cria perfil minimo (external_id + cpf)."""
        resp = await self._request(
            "POST",
            "/api/v1/profiles",
            json={"external_id": external_id, "cpf": cpf},
        )
        return resp.json()

    async def check_cpf(self, cpf: str) -> dict:
        """GET /api/v1/profiles/cpf/{cpf} → {external_id, found, valid}."""
        resp = await self._request("GET", f"/api/v1/profiles/cpf/{cpf}")
        return resp.json()

    async def get_one(self, external_id: str) -> dict:
        """GET /api/v1/profiles/{external_id} — perfil completo."""
        resp = await self._request("GET", f"/api/v1/profiles/{external_id}")
        return resp.json()

    async def patch_field(self, external_id: str, field: str, value: str) -> dict:
        """PATCH /api/v1/profiles/{external_id}/{field}?value= — atualiza campo."""
        resp = await self._request(
            "PATCH",
            f"/api/v1/profiles/{external_id}/{field}",
            params={"value": value},
        )
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
        safe_url = _redact_cpf_from_url(url)
        safe = _sanitize_log_body(json, {"cpf"})
        logger.debug(f"[profiles] {method} {safe_url}" + (f" body={safe}" if safe else ""))
        resp = await self._session.request(
            method,
            url,
            json=json,
            params=params,
            timeout=self._timeout,
        )
        logger.debug(f"[profiles] ← {resp.status_code}")
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
            raise ProfilesError(resp.status_code, detail)
        return resp


class ProfilesError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        self.status = status
        self.detail = detail
        super().__init__(f"[{status}] {detail}")
