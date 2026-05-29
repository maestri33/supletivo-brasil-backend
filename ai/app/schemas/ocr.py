"""Schemas de OCR / Google Vision — endpoints /ocr/."""

from pydantic import BaseModel, Field


class OCRResponse(BaseModel):
    """Resultado da extracao de texto de imagem."""

    text: str = Field(description="Texto extraido completo")
    locale: str | None = Field(description="Idioma detectado")
    pages: list = Field(description="Estrutura paginas/blocos/paragrafos/palavras")
