"""Client HTTP para o Notify Service (notify.local)."""

from __future__ import annotations

import niquests

from app.config import get_settings
from app.utils.logconfig import get_logger

logger = get_logger(__name__)


def _sanitize_log_body(body: dict | None, sensitive: set[str]) -> dict | None:
    """Remove sensitive fields from log output."""
    if not isinstance(body, dict):
        return body
    return {k: ("***" if k in sensitive else v) for k, v in body.items()}


class NotifyClient:
    """Async HTTP client para o Notify Service — contacts."""

    def __init__(self, base_url: str | None = None, timeout: int = 10) -> None:
        self._base = (base_url or get_settings().NOTIFY_SERVICE_URL).rstrip("/")
        self._timeout = timeout

    async def __aenter__(self) -> NotifyClient:
        self._session = niquests.AsyncSession()
        self._session.headers.update({"Accept": "application/json"})
        return self

    async def __aexit__(self, *args: object) -> None:
        await self._session.close()

    # ── Contacts ───────────────────────────────────

    async def check_contact(
        self,
        phone: str | None = None,
        email: str | None = None,
    ) -> dict:
        """GET /api/v1/contacts/check — verifica existencia e valida phone/email."""
        params: dict[str, str] = {}
        if phone:
            params["phone"] = phone
        if email:
            params["email"] = email
        resp = await self._request("GET", "/api/v1/contacts/check", params=params)
        return resp.json()

    async def get_contact(self, external_id: str) -> dict:
        """GET /api/v1/contacts/{external_id} — busca contato por external_id."""
        resp = await self._request("GET", f"/api/v1/contacts/{external_id}")
        return resp.json()

    async def create_contact(
        self,
        external_id: str,
        phone: str | None = None,
        email: str | None = None,
    ) -> dict:
        """POST /api/v1/contacts — cria contacto."""
        body: dict[str, str] = {"external_id": external_id}
        if phone:
            body["phone"] = phone
        if email:
            body["email"] = email
        resp = await self._request("POST", "/api/v1/contacts", json=body)
        return resp.json()

    # ── Internal ────────────────────────────────────

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        params: dict | None = None,
    ) -> niquests.Response:
        url = f"{self._base}{path}"
        safe = _sanitize_log_body(json, {"phone", "email"})
        logger.debug(f"[notify] {method} {url}" + (f" body={safe}" if safe else ""))
        resp = await self._session.request(
            method,
            url,
            json=json,
            params=params,
            timeout=self._timeout,
        )
        logger.debug(f"[notify] ← {resp.status_code}")
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
            raise NotifyError(resp.status_code, detail)
        return resp


class NotifyError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        self.status = status
        self.detail = detail
        super().__init__(f"[{status}] {detail}")
