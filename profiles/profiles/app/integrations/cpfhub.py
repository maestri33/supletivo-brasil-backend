"""Cliente HTTP para a CPFHub.io — lookup de identidade por CPF.

Best-effort: qualquer falha (rede, timeout, 4xx, 5xx, parse) retorna None.
O caller decide se ignora ou propaga. Por contrato, este módulo NUNCA levanta.

Não loga CPF nem nome (PII). Apenas status/erro agregado.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import date

import httpx

from app.utils.logging import get_logger

logger = get_logger(__name__)

# Status HTTP que justificam retry (transient).
_RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})

# Backoff em segundos entre tentativas. len = retries (3 tentativas totais).
_RETRY_DELAYS = (0.2, 0.8)


@dataclass(frozen=True)
class CPFHubIdentity:
    """Identidade retornada pela CPFHub. Todos os campos são opcionais."""

    name: str | None = None
    gender: str | None = None
    birth_date: date | None = None

    def is_empty(self) -> bool:
        return self.name is None and self.gender is None and self.birth_date is None


def _parse_identity(data: dict) -> CPFHubIdentity | None:
    """Extrai campos relevantes do payload `data` da CPFHub. None se nada útil."""
    name = data.get("name")
    if isinstance(name, str):
        name = name.strip() or None
    else:
        name = None

    gender_raw = data.get("gender")
    gender = gender_raw if gender_raw in ("M", "F") else None

    birth_date: date | None = None
    day = data.get("day")
    month = data.get("month")
    year = data.get("year")
    if isinstance(day, int) and isinstance(month, int) and isinstance(year, int):
        try:
            birth_date = date(year, month, day)
        except ValueError:
            birth_date = None

    identity = CPFHubIdentity(name=name, gender=gender, birth_date=birth_date)
    return None if identity.is_empty() else identity


class CPFHubClient:
    """Async context manager. Use via `async with CPFHubClient(...) as client:`."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.cpfhub.io",
        timeout: float = 5.0,
    ) -> None:
        self._api_key = api_key
        self._base = base_url.rstrip("/")
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> CPFHubClient:
        self._client = httpx.AsyncClient(
            timeout=self._timeout,
            headers={
                "x-api-key": self._api_key,
                "Accept": "application/json",
            },
        )
        return self

    async def __aexit__(self, *args: object) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def lookup(self, cpf: str) -> CPFHubIdentity | None:
        """GET /cpf/{cpf}. Retorna identidade ou None em qualquer falha."""
        if self._client is None:
            logger.warning("cpfhub.not_initialized")
            return None
        if not self._api_key:
            logger.warning("cpfhub.no_api_key")
            return None

        digits = re.sub(r"[^0-9]", "", cpf or "")
        if len(digits) != 11:
            logger.warning("cpfhub.invalid_cpf_format", digits_len=len(digits))
            return None

        url = f"{self._base}/cpf/{digits}"
        max_attempts = len(_RETRY_DELAYS) + 1
        resp: httpx.Response | None = None

        for attempt in range(max_attempts):
            try:
                resp = await self._client.get(url)
            except (httpx.TimeoutException, httpx.NetworkError, httpx.RequestError) as exc:
                logger.warning(
                    "cpfhub.request_error",
                    attempt=attempt,
                    error=type(exc).__name__,
                )
                if attempt + 1 < max_attempts:
                    await asyncio.sleep(_RETRY_DELAYS[attempt])
                    continue
                return None

            if resp.status_code in _RETRY_STATUSES and attempt + 1 < max_attempts:
                logger.warning(
                    "cpfhub.transient_status",
                    attempt=attempt,
                    status=resp.status_code,
                )
                await asyncio.sleep(_RETRY_DELAYS[attempt])
                continue

            break

        if resp is None:
            return None

        if resp.status_code != 200:
            logger.warning("cpfhub.non_200", status=resp.status_code)
            return None

        try:
            body = resp.json()
        except ValueError:
            logger.warning("cpfhub.invalid_json")
            return None

        if not isinstance(body, dict) or not body.get("success"):
            logger.info("cpfhub.lookup_unsuccessful")
            return None

        data = body.get("data")
        if not isinstance(data, dict):
            return None

        return _parse_identity(data)
