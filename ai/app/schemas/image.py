"""Schemas de imagem / Gemini — endpoints /image/."""

from pydantic import BaseModel, Field


class ImageRequest(BaseModel):
    """Geracao de imagem."""

    prompt: str = Field(description="Descricao da imagem a ser gerada")
    negative_prompt: str | None = Field(
        default=None, description="O que evitar na imagem"
    )
    aspect_ratio: str = Field(
        default="1:1", description="Proporcao (1:1, 3:4, 16:9, 9:16)"
    )
    people_generation: str = Field(
        default="allow", description="Permitir geracao de pessoas (allow, dont_allow)"
    )


class ImageResponse(BaseModel):
    """URL da imagem gerada."""

    url: str


class VisionRequest(BaseModel):
    """Descricao de imagem via Gemini Vision."""

    prompt: str = Field(description="O que perguntar sobre a imagem")
    image_b64: str = Field(description="Conteudo da imagem em base64")


class VisionResponse(BaseModel):
    """Descricao textual da imagem."""

    description: str
