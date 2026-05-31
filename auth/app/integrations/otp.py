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


class OTPClient:
    """Async HTTP client para o OTP Service — geracao e validacao de OTP."""

    def __init__(self, base_url: str | None = None, timeout: int = 10) -> None:
        self._base = (base_url or get_settings().OTP_SERVICE_URL).rstrip("/")
        self._timeout = timeout

    async def __aenter__(self) -> OTPClient:
        self._session = httpx.AsyncClient(headers={"Accept": "application/json"})
        return self

    async def __aexit__(self, *args: object) -> None:
        await self._session.aclose()

    async def create(self, external_id: str) -> dict:
        """POST /api/v1/otp — gera OTP e envia via Notify."""
        resp = await self._request("POST", "/api/v1/otp", json={"external_id": external_id})
        return resp.json()

    async def check(self, external_id: str, code: str) -> dict:
        """POST /api/v1/otp/check — valida codigo OTP."""
        resp = await self._request(
            "POST",
            "/api/v1/otp/check",
            json={"external_id": external_id, "code": code},
        )
        return resp.json()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        params: dict | None = None,
    ) -> httpx.Response:
        url = f"{self._base}{path}"
        safe = _sanitize_log_body(json, {"code"})
        logger.debug(f"[otp] {method} {url}" + (f" body={safe}" if safe else ""))
        resp = await self._session.request(
            method,
            url,
            json=json,
            params=params,
            timeout=self._timeout,
        )
        logger.debug(f"[otp] ← {resp.status_code}")
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
            raise OTPError(resp.status_code, detail)
        return resp


class OTPError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        self.status = status
        self.detail = detail
        super().__init__(f"[{status}] {detail}")
