"""
Cliente HTTP async para o microservico profiles.

Atualmente usado apenas para descobrir gender (M/F) na escolha de voz TTS.
Falhas (HTTP, conexao, 404, shape invalido) NUNCA propagam — retornam None
para que o caller siga com a voz default. TTS nao deve quebrar por falha
de lookup de profile.
"""

from __future__ import annotations

import httpx

from app.config import get_settings
from app.utils.logging import get_logger

log = get_logger(__name__)


class ProfilesClient:
    """Cliente para profiles (http://profiles:8000)."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client
        settings = get_settings()
        self._base = settings.profiles_base_url.rstrip("/")
        self._timeout = settings.profiles_timeout_s

    async def get_gender(self, external_id: str) -> str | None:
        """Retorna 'M', 'F' ou None.

        None significa: profile nao existe, gender nao informado, ou lookup
        falhou. O caller deve usar voz default nesse caso.
        """
        url = f"{self._base}/api/v1/profiles/{external_id}"
        try:
            resp = await self._client.get(url, timeout=self._timeout)
        except httpx.HTTPError as exc:
            log.warning("profiles.lookup_failed", external_id=external_id, error=str(exc))
            return None

        if resp.status_code == 404:
            log.info("profiles.not_found", external_id=external_id)
            return None
        if resp.status_code >= 400:
            log.warning(
                "profiles.lookup_http_error",
                external_id=external_id,
                status=resp.status_code,
            )
            return None

        try:
            body = resp.json()
            gender = body.get("gender")
        except (ValueError, AttributeError) as exc:
            log.warning("profiles.shape_invalid", external_id=external_id, error=str(exc))
            return None

        if gender not in ("M", "F"):
            return None
        return gender
