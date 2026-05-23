"""
Cliente para o microservico AI — texto, imagem, TTS, JSON.

Servico: ai (10.10.10.177)
Endpoints: POST /text/, /image/, /image/vision, /tts/, /json/
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from app.config import get_settings
from app.exceptions import IntegrationError
from app.integrations.http_client import request_with_retry
from app.utils.logging import get_logger

log = get_logger(__name__)

MEDIA_DIR = Path("media")


class AIClient:
    """Cliente HTTP para o servico AI — substitui DeepSeek + ElevenLabs + Gemini."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client
        self._base = get_settings().ai_base_url

    # ------------------------------------------------------------------
    # Texto
    # ------------------------------------------------------------------

    async def text(
        self,
        prompt: str,
        *,
        instruction: str | None = None,
    ) -> str:
        """Gera texto. Retorna a string do texto gerado."""
        body: dict = {"prompt": prompt}
        if instruction:
            body["instruction"] = instruction
        resp = await request_with_retry(
            self._client, "POST", f"{self._base}/text/",
            json=body, timeout=60.0,
        )
        if resp.status_code >= 400:
            raise IntegrationError(f"AI /text falhou ({resp.status_code}): {resp.text}")
        return resp.json()["text"]

    # ------------------------------------------------------------------
    # Imagem
    # ------------------------------------------------------------------

    async def image(
        self,
        prompt: str,
        *,
        reference_url: str | None = None,
    ) -> dict[str, Any]:
        """Gera/edita imagem. Retorna o primeiro item de 'images': {url, filename, mime_type}."""
        body: dict = {"prompt": prompt}
        if reference_url:
            body["reference_url"] = reference_url
        resp = await request_with_retry(
            self._client, "POST", f"{self._base}/image/",
            json=body, timeout=120.0,
        )
        if resp.status_code >= 400:
            raise IntegrationError(f"AI /image falhou ({resp.status_code}): {resp.text}")
        data = resp.json()
        images = data.get("images", [])
        if not images:
            raise IntegrationError("AI /image retornou array vazio")
        return images[0]

    async def download_image(self, image_url: str) -> tuple[bytes, str]:
        """Baixa imagem gerada, retorna (bytes, filename)."""
        resp = await self._client.get(image_url, timeout=30.0)
        if resp.status_code >= 400:
            raise IntegrationError(f"Download imagem falhou ({resp.status_code})")
        filename = image_url.rsplit("/", 1)[-1]
        return resp.content, filename

    async def save_image_locally(self, image_url: str) -> str:
        """Baixa imagem do AI e salva em data/public/imagem/. Retorna path relativo."""
        data, filename = await self.download_image(image_url)
        out = MEDIA_DIR / "imagem"
        out.mkdir(parents=True, exist_ok=True)
        (out / filename).write_bytes(data)
        log.info("ai.image_saved_locally", filename=filename)
        return f"imagem/{filename}"

    # ------------------------------------------------------------------
    # TTS
    # ------------------------------------------------------------------

    async def tts(self, text: str, *, voice_id: str | None = None) -> dict[str, str]:
        """Texto para voz. Retorna {url, filename}.

        voice_id: override do voice_id no AI service. None -> AI usa default.
        """
        body: dict = {"text": text}
        if voice_id:
            body["voice_id"] = voice_id
        resp = await request_with_retry(
            self._client, "POST", f"{self._base}/tts/",
            json=body,
            timeout=120.0,
        )
        if resp.status_code >= 400:
            raise IntegrationError(f"AI /tts falhou ({resp.status_code}): {resp.text}")
        return resp.json()

    async def download_audio(self, audio_url: str) -> tuple[bytes, str]:
        """Baixa audio gerado, retorna (bytes, filename)."""
        resp = await self._client.get(audio_url, timeout=30.0)
        if resp.status_code >= 400:
            raise IntegrationError(f"Download audio falhou ({resp.status_code})")
        filename = audio_url.rsplit("/", 1)[-1]
        return resp.content, filename

    async def save_audio_locally(self, audio_url: str) -> str:
        """Baixa audio do AI e salva em data/public/audio/. Retorna path relativo."""
        data, filename = await self.download_audio(audio_url)
        out = MEDIA_DIR / "audio"
        out.mkdir(parents=True, exist_ok=True)
        (out / filename).write_bytes(data)
        log.info("ai.audio_saved_locally", filename=filename)
        return f"audio/{filename}"

    # ------------------------------------------------------------------
    # JSON
    # ------------------------------------------------------------------

    async def json(
        self,
        prompt: str,
        *,
        instruction: str | None = None,
        schema_description: str | None = None,
    ) -> dict[str, Any]:
        """Gera JSON estruturado. Retorna {data: {...}}."""
        resp = await request_with_retry(
            self._client, "POST", f"{self._base}/json/",
            json={
                "prompt": prompt,
                "instruction": instruction,
                "schema_description": schema_description,
            },
            timeout=60.0,
        )
        if resp.status_code >= 400:
            raise IntegrationError(f"AI /json falhou ({resp.status_code}): {resp.text}")
        return resp.json()["data"]
