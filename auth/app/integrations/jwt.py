"""Client HTTP para o JWT Service (jwt.local)."""

from __future__ import annotations

import logging

import niquests

from app.config import get_settings

logger = logging.getLogger(__name__)


class JWTClient:
    """Async HTTP client para o JWT Service — tokens + JWKS."""

    def __init__(self, base_url: str | None = None, timeout: int = 10) -> None:
        self._base = (base_url or get_settings().JWT_SERVICE_URL).rstrip("/")
        self._timeout = timeout

    async def __aenter__(self) -> JWTClient:
        self._session = niquests.AsyncSession()
        self._session.headers.update({"Accept": "application/json"})
        return self

    async def __aexit__(self, *args: object) -> None:
        await self._session.close()

    # ── Tokens ──────────────────────────────────────

    async def issue(self, external_id: str, roles: list[str]) -> dict:
        """POST /api/v1/tokens/issue — emite access + refresh token."""
        resp = await self._request(
            "POST",
            "/api/v1/tokens/issue",
            json={"external_id": external_id, "roles": roles},
        )
        return resp.json()

    async def refresh(self, refresh_token: str) -> dict:
        """POST /api/v1/tokens/refresh — renova par de tokens."""
        resp = await self._request(
            "POST",
            "/api/v1/tokens/refresh",
            json={"refresh_token": refresh_token},
        )
        return resp.json()

    # ── JWKS ────────────────────────────────────────

    async def get_jwks(self) -> dict:
        """GET /.well-known/jwks.json — chaves publicas no formato JWKS."""
        resp = await self._request("GET", "/.well-known/jwks.json")
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
        logger.debug(f"[jwt] {method} {url}" + (f" body={json}" if json else ""))
        resp = await self._session.request(
            method,
            url,
            json=json,
            params=params,
            timeout=self._timeout,
        )
        logger.debug(f"[jwt] ← {resp.status_code}")
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
            raise JWTError(resp.status_code, detail)
        return resp


class JWTError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        self.status = status
        self.detail = detail
        super().__init__(f"[{status}] {detail}")
