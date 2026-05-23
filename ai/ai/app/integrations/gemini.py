"""
Cliente Gemini — geracao e edicao de imagens + visao.
Usa o SDK google-genai oficial (client.aio.models.generate_content).
"""

import uuid

import httpx
from google import genai
from google.genai import errors as genai_errors, types

from app.config import get_settings
from app.integrations.http_client import IntegrationError
from app.utils.logging import get_logger

log = get_logger(__name__)

ALLOWED_MIME = {"image/png", "image/jpeg", "image/webp"}


class GeminiClient:
    """Cliente para Gemini (geracao de imagem + visao)."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        settings = get_settings()
        self._http = client  # httpx para download de referencias
        self._genai = genai.Client(api_key=settings.gemini_api_key)
        self._image_model = settings.gemini_image_model
        self._vision_model = settings.gemini_vision_model

    async def generate_image(
        self,
        prompt: str,
        *,
        reference_url: str | None = None,
        aspect_ratio: str | None = None,
        image_size: str | None = None,
        google_search: bool = False,
    ) -> tuple[bytes, str]:
        """Gera uma imagem. Retorna (bytes, mime_type)."""
        parts: list = [types.Part(text=prompt)]

        if reference_url:
            ref_bytes, ref_mime = await self._download_reference(reference_url)
            parts.append(types.Part(inline_data=types.Blob(mime_type=ref_mime, data=ref_bytes)))

        image_config = types.ImageConfig()
        if aspect_ratio:
            image_config.aspect_ratio = aspect_ratio
        if image_size:
            image_config.image_size = image_size

        tools = [types.Tool(google_search=types.GoogleSearch())] if google_search else None

        config = types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=image_config,
            tools=tools,
        )

        try:
            response = await self._genai.aio.models.generate_content(
                model=self._image_model,
                contents=[types.Content(parts=parts)],
                config=config,
            )
        except genai_errors.APIError as exc:
            raise IntegrationError(f"Gemini imagem falhou: {exc}") from exc

        for part in response.parts:
            if part.inline_data and part.inline_data.data:
                mime = part.inline_data.mime_type or "image/png"
                data = part.inline_data.data
                log.info("gemini.image_generated", mime=mime, size=len(data))
                return data, mime

        raise IntegrationError("Gemini nao retornou imagem")

    async def _download_reference(self, url: str) -> tuple[bytes, str]:
        resp = await self._http.get(
            url,
            timeout=30.0,
            follow_redirects=True,
            headers={"User-Agent": "v7m-ai/1.0"},
        )
        if resp.status_code >= 400:
            raise IntegrationError(f"Download referencia falhou ({resp.status_code})")
        # content-type pode vir com charset: "image/jpeg; charset=binary"
        raw_mime = resp.headers.get("content-type", "image/png")
        mime = raw_mime.split(";")[0].strip().lower()
        if mime not in ALLOWED_MIME:
            mime = "image/png"
        return resp.content, mime

    async def describe(self, image_url: str) -> str:
        """Descreve uma imagem via Gemini Vision."""
        img_bytes, img_mime = await self._download_reference(image_url)

        try:
            response = await self._genai.aio.models.generate_content(
                model=self._vision_model,
                contents=[
                    types.Part.from_text(text="Descreva esta imagem em portugues brasileiro de forma clara e objetiva."),
                    types.Part.from_bytes(data=img_bytes, mime_type=img_mime),
                ],
            )
        except genai_errors.APIError as exc:
            raise IntegrationError(f"Gemini vision falhou: {exc}") from exc

        text = response.text or ""
        log.info("gemini.vision_done", length=len(text), bytes=len(img_bytes), mime=img_mime)
        return text.strip()

    def image_filename(self, mime_type: str) -> str:
        ext_map = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
        return f"{uuid.uuid4()}{ext_map.get(mime_type, '.png')}"
