"""
POST /tts/ — text-to-speech via ElevenLabs.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.config import get_settings
from app.integrations.elevenlabs import ElevenLabsClient
from app.integrations.http_client import get_http_client
from app.utils.media import save_media

router = APIRouter(prefix="/tts", tags=["tts"])


class TTSRequest(BaseModel):
    text: str


class TTSResponse(BaseModel):
    url: str
    filename: str


def _media_url(filename: str) -> str:
    return f"{get_settings().public_base_url}/media/audio/{filename}"


@router.post("/", response_model=TTSResponse)
async def generate_tts(body: TTSRequest, client=Depends(get_http_client)):
    tts = ElevenLabsClient(client)
    audio = await tts.generate(body.text)
    filename = tts.audio_filename()
    save_media("audio", filename, audio)

    return TTSResponse(url=_media_url(filename), filename=filename)
