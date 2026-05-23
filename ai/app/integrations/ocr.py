"""
Cliente Google Cloud Vision OCR — deteccao de texto em imagens.
Suporta TEXT_DETECTION (texto generico) e DOCUMENT_TEXT_DETECTION (documentos densos).
"""

from dataclasses import dataclass

from google.cloud import vision
from google.cloud.vision_v1 import ImageAnnotatorClient

from app.config import get_settings
from app.integrations.http_client import IntegrationError
from app.utils.logging import get_logger

log = get_logger(__name__)


@dataclass
class OCRResult:
    text: str
    pages: list[dict]
    locale: str | None = None


def _build_client() -> ImageAnnotatorClient:
    settings = get_settings()
    if settings.google_vision_service_account_json:
        return ImageAnnotatorClient.from_service_account_json(
            settings.google_vision_service_account_json,
        )
    if settings.google_vision_api_key:
        return ImageAnnotatorClient(client_options={
            "api_key": settings.google_vision_api_key,
        })
    raise IntegrationError(
        "Configure GOOGLE_VISION_API_KEY ou GOOGLE_VISION_SERVICE_ACCOUNT_JSON no .env"
    )


class VisionOCRClient:
    def __init__(self) -> None:
        self._client = _build_client()

    def _image_from_bytes(self, data: bytes) -> vision.Image:
        return vision.Image(content=data)

    def detect_text(self, data: bytes, language_hints: list[str] | None = None) -> OCRResult:
        image = self._image_from_bytes(data)
        image_context = vision.ImageContext(language_hints=language_hints) if language_hints else None

        response = self._client.text_detection(image=image, image_context=image_context)

        if response.error.message:
            raise IntegrationError(f"Vision OCR falhou: {response.error.message}")

        return self._parse_response(response)

    def detect_document_text(self, data: bytes, language_hints: list[str] | None = None) -> OCRResult:
        image = self._image_from_bytes(data)
        image_context = vision.ImageContext(language_hints=language_hints) if language_hints else None

        response = self._client.document_text_detection(image=image, image_context=image_context)

        if response.error.message:
            raise IntegrationError(f"Vision Document OCR falhou: {response.error.message}")

        return self._parse_response(response)

    def detect_text_uri(self, uri: str, language_hints: list[str] | None = None) -> OCRResult:
        image = vision.Image(source=vision.ImageSource(image_uri=uri))
        image_context = vision.ImageContext(language_hints=language_hints) if language_hints else None

        response = self._client.text_detection(image=image, image_context=image_context)

        if response.error.message:
            raise IntegrationError(f"Vision OCR falhou: {response.error.message}")

        return self._parse_response(response)

    def _parse_response(self, response) -> OCRResult:
        full_text = response.full_text_annotation
        pages = []

        for page in full_text.pages:
            page_dict = {
                "width": page.width,
                "height": page.height,
                "blocks": [],
            }
            for block in page.blocks:
                block_dict = {
                    "block_type": str(block.block_type),
                    "paragraphs": [],
                }
                for para in block.paragraphs:
                    para_text = "".join(
                        word.symbols[0].text if len(word.symbols) == 0
                        else "".join(s.text for s in word.symbols)
                        for word in para.words
                    )
                    block_dict["paragraphs"].append({
                        "text": para_text,
                        "confidence": para.confidence,
                        "words": [
                            {
                                "text": "".join(s.text for s in word.symbols),
                                "confidence": word.confidence,
                            }
                            for word in para.words
                        ],
                    })
                page_dict["blocks"].append(block_dict)
            pages.append(page_dict)

        locale = full_text.text if full_text else None

        texts = response.text_annotations
        full_description = texts[0].description if texts else ""
        detected_locale = texts[0].locale if texts else None

        return OCRResult(
            text=full_description,
            pages=pages,
            locale=detected_locale or locale,
        )

    def close(self) -> None:
        try:
            self._client.transport.close()
        except Exception:
            pass
