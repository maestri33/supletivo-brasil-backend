"""
POST /image/ — geracao/edicao de imagem via Gemini.
POST /image/vision — descrever imagem via Gemini Vision.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.config import get_settings
from app.integrations.gemini import GeminiClient
from app.integrations.deepseek import DeepSeekClient
from app.integrations.http_client import get_http_client
from app.utils.media import save_media

router = APIRouter(prefix="/image", tags=["image"])


class ImageRequest(BaseModel):
    prompt: str
    instruction: str | None = None
    reference_url: str | None = None


class ImageResponse(BaseModel):
    url: str
    filename: str
    mime_type: str


class VisionRequest(BaseModel):
    image_url: str


class VisionResponse(BaseModel):
    description: str


def _media_url(filename: str) -> str:
    return f"{get_settings().public_base_url}/media/image/{filename}"


@router.post("/", response_model=ImageResponse)
async def generate_image(body: ImageRequest, client=Depends(get_http_client)):
    gemini = GeminiClient(client)

    prompt = body.prompt
    if body.instruction:
        ds = DeepSeekClient(client)
        prompt = (await ds.generate_json(
            f"Gere um prompt de imagem para: {body.prompt}",
            instruction=body.instruction,
            schema_description="prompt: string (max 300 chars, visual, cores, estilo)",
        )).get("prompt", body.prompt)

    data, mime = await gemini.generate_image(prompt, reference_url=body.reference_url)
    filename = gemini.image_filename(mime)
    save_media("image", filename, data)

    return ImageResponse(url=_media_url(filename), filename=filename, mime_type=mime)


@router.post("/vision", response_model=VisionResponse)
async def describe_image(body: VisionRequest, client=Depends(get_http_client)):
    gemini = GeminiClient(client)
    description = await gemini.describe(body.image_url)
    return VisionResponse(description=description)
