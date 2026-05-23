"""
POST /ocr/ — extrair texto de imagem via Google Cloud Vision OCR.
POST /ocr/document — OCR otimizado para documentos densos.
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel, Field

from app.integrations.ocr import VisionOCRClient
from app.utils.logging import get_logger

log = get_logger(__name__)

router = APIRouter(tags=["ocr"])


class OCRResponse(BaseModel):
    text: str = Field(description="Texto extraido completo")
    locale: str | None = Field(description="Idioma detectado")
    pages: list = Field(description="Estrutura paginas/blocos/paragrafos/palavras")


@router.post("/", response_model=OCRResponse)
async def ocr_text(
    file: UploadFile = File(description="Imagem (PNG, JPEG, WEBP, GIF, BMP, TIFF)"),
    language_hints: str | None = Form(default=None, description="Hints de idioma separados por virgula: pt,en,es"),
):
    data = await file.read()
    if not data:
        raise HTTPException(400, "Arquivo vazio")

    hints = [h.strip() for h in language_hints.split(",") if h.strip()] if language_hints else None

    client = VisionOCRClient()
    try:
        result = client.detect_text(data, language_hints=hints)
    except Exception as exc:
        log.error("ocr.failed", error=str(exc))
        raise HTTPException(502, f"OCR falhou: {exc}") from exc
    finally:
        client.close()

    log.info("ocr.done", chars=len(result.text), locale=result.locale)
    return OCRResponse(text=result.text, locale=result.locale, pages=result.pages)


@router.post("/document", response_model=OCRResponse)
async def ocr_document(
    file: UploadFile = File(description="Documento/imagem (PNG, JPEG, PDF, TIFF)"),
    language_hints: str | None = Form(default=None, description="Hints de idioma separados por virgula: pt,en,es"),
):
    data = await file.read()
    if not data:
        raise HTTPException(400, "Arquivo vazio")

    hints = [h.strip() for h in language_hints.split(",") if h.strip()] if language_hints else None

    client = VisionOCRClient()
    try:
        result = client.detect_document_text(data, language_hints=hints)
    except Exception as exc:
        log.error("ocr.document.failed", error=str(exc))
        raise HTTPException(502, f"OCR document falhou: {exc}") from exc
    finally:
        client.close()

    log.info("ocr.document_done", chars=len(result.text), locale=result.locale)
    return OCRResponse(text=result.text, locale=result.locale, pages=result.pages)
