"""
Cliente Gemini — geracao e edicao de imagens.
"""

import base64
import uuid
import logging

import httpx

from app.config import get_settings
from app.integrations.http_client import IntegrationError, request_with_retry

log = logging.getLogger(__name__)

ALLOWED_MIME = {"image/png", "image/jpeg", "image/webp"}


class GeminiClient:
    """Cliente para Gemini (geracao de imagem + visao)."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        settings = get_settings()
        self._client = client
        self._api_key = settings.gemini_api_key
        self._base_url = settings.gemini_base_url
        self._image_model = settings.gemini_image_model
        self._vision_model = settings.gemini_vision_model

    def _url(self, model: str) -> str:
        return f"{self._base_url}/{model}:generateContent"

    def _headers(self) -> dict[str, str]:
        return {"x-goog-api-key": self._api_key}

    async def generate_image(
        self,
        prompt: str,
        *,
        reference_url: str | None = None,
    ) -> tuple[bytes, str]:
        """Gera uma imagem. Retorna (bytes, mime_type)."""
        parts: list[dict] = [{"text": prompt}]

        if reference_url:
            ref_bytes, ref_mime = await self._download_reference(reference_url)
            parts.append({
                "inline_data": {"mime_type": ref_mime, "data": base64.b64encode(ref_bytes).decode()}
            })

        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {"responseModalities": ["IMAGE"]},
        }

        resp = await request_with_retry(
            self._client, "POST",
            self._url(self._image_model),
            json=payload,
            headers=self._headers(),
            timeout=120.0,
        )
        if resp.status_code >= 400:
            raise IntegrationError(f"Gemini imagem falhou ({resp.status_code}): {resp.text}")

        body = resp.json()
        for part in body.get("candidates", [{}])[0].get("content", {}).get("parts", []):
            inline = part.get("inlineData")
            if inline:
                mime = inline.get("mimeType", "image/png")
                data = base64.b64decode(inline["data"])
                log.info("gemini.image_generated", mime=mime, size=len(data))
                return data, mime

        raise IntegrationError("Gemini nao retornou imagem")

    async def _download_reference(self, url: str) -> tuple[bytes, str]:
        resp = await self._client.get(url, timeout=30.0)
        if resp.status_code >= 400:
            raise IntegrationError(f"Download referencia falhou ({resp.status_code})")
        mime = resp.headers.get("content-type", "image/png")
        if mime not in ALLOWED_MIME:
            mime = "image/png"
        return resp.content, mime

    async def describe(self, image_url: str) -> str:
        """Descreve uma imagem via Gemini Vision."""
        img_bytes, img_mime = await self._download_reference(image_url)
        payload = {
            "contents": [{
                "parts": [
                    {"text": "Descreva esta imagem em portugues brasileiro de forma clara e objetiva."},
                    {"inline_data": {"mime_type": img_mime, "data": base64.b64encode(img_bytes).decode()}},
                ]
            }]
        }
        resp = await request_with_retry(
            self._client, "POST",
            self._url(self._vision_model),
            json=payload,
            headers=self._headers(),
            timeout=60.0,
        )
        if resp.status_code >= 400:
            raise IntegrationError(f"Gemini vision falhou ({resp.status_code}): {resp.text}")

        body = resp.json()
        text = body.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        log.info("gemini.vision_done", length=len(text))
        return text.strip()

    def image_filename(self, mime_type: str) -> str:
        ext_map = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
        return f"{uuid.uuid4()}{ext_map.get(mime_type, '.png')}"
