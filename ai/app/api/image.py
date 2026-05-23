"""
POST /image/ — geracao de imagem via Gemini.
POST /image/vision — descrever imagem via Gemini Vision.
"""

import asyncio

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.integrations.gemini import GeminiClient
from app.integrations.http_client import get_http_client
from app.utils.media import media_url, save_media

router = APIRouter(tags=["image"])


class ImageRequest(BaseModel):
    prompt: str = Field(description="Descricao da imagem a ser gerada")
    reference_url: str | None = Field(default=None, description="URL de imagem de referencia para edicao")
    aspect_ratio: str | None = Field(default=None, description="Proporcao (ex: '16:9', '4:3', '1:1')")
    image_size: str | None = Field(default=None, description="Resolucao (ex: '2K', '4K')")
    google_search: bool = Field(default=False, description="Ativa grounding com Google Search")
    num_images: int = Field(default=1, ge=1, le=4, description="Quantas imagens gerar em paralelo (1-4)")


class ImageItem(BaseModel):
    url: str
    filename: str
    mime_type: str


class ImageResponse(BaseModel):
    images: list[ImageItem]


class VisionRequest(BaseModel):
    image_url: str


class VisionResponse(BaseModel):
    description: str


@router.post("/", response_model=ImageResponse)
async def generate_image(body: ImageRequest, client=Depends(get_http_client)):
    gemini = GeminiClient(client)

    if body.num_images > 1:
        results = await asyncio.gather(*(
            gemini.generate_image(
                body.prompt,
                reference_url=body.reference_url,
                aspect_ratio=body.aspect_ratio,
                image_size=body.image_size,
                google_search=body.google_search,
            )
            for _ in range(body.num_images)
        ))
    else:
        results = [await gemini.generate_image(
            body.prompt,
            reference_url=body.reference_url,
            aspect_ratio=body.aspect_ratio,
            image_size=body.image_size,
            google_search=body.google_search,
        )]

    images: list[ImageItem] = []
    for data, mime in results:
        filename = gemini.image_filename(mime)
        save_media("image", filename, data)
        images.append(ImageItem(url=media_url("image", filename), filename=filename, mime_type=mime))

    return ImageResponse(images=images)


@router.post("/vision", response_model=VisionResponse)
async def describe_image(body: VisionRequest, client=Depends(get_http_client)):
    gemini = GeminiClient(client)
    description = await gemini.describe(body.image_url)
    return VisionResponse(description=description)
