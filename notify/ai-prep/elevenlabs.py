"""
Cliente ElevenLabs — text-to-speech.
"""

import uuid

import httpx

from app.config import get_settings
from app.integrations.http_client import IntegrationError, request_with_retry
from app.utils.logging import get_logger

log = get_logger(__name__)


class ElevenLabsClient:
    """Cliente para ElevenLabs TTS."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        settings = get_settings()
        self._client = client
        self._api_key = settings.elevenlabs_api_key
        self._voice_id = settings.elevenlabs_voice_id
        self._model_id = settings.elevenlabs_model_id
        self._output_format = settings.elevenlabs_output_format
        self._base_url = "https://api.elevenlabs.io"

    def _headers(self) -> dict[str, str]:
        return {"xi-api-key": self._api_key}

    async def generate(self, text: str) -> bytes:
        """Gera audio a partir de texto, retorna bytes MP3."""
        url = f"{self._base_url}/v1/text-to-speech/{self._voice_id}"
        payload = {
            "text": text,
            "model_id": self._model_id,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        }
        params = {"output_format": self._output_format}

        resp = await request_with_retry(
            self._client, "POST", url,
            json=payload,
            params=params,
            headers=self._headers(),
            timeout=120.0,
        )
        if resp.status_code >= 400:
            raise IntegrationError(f"ElevenLabs falhou ({resp.status_code}): {resp.text}")

        log.info("elevenlabs.audio_generated", text_len=len(text), audio_size=len(resp.content))
        return resp.content

    def audio_filename(self) -> str:
        return f"{uuid.uuid4()}.mp3"
