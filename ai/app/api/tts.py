"""
POST /tts/ — text-to-speech via ElevenLabs.
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.integrations.elevenlabs import ElevenLabsClient
from app.utils.media import media_url, save_media

router = APIRouter(tags=["tts"])


class TTSRequest(BaseModel):
    text: str = Field(description="Texto a ser convertido em fala")
    voice_id: str | None = Field(
        default=None,
        description="Override do voice_id do ElevenLabs. Se None, usa elevenlabs_voice_id do settings.",
    )
    speed: float | None = Field(default=None, ge=0.25, le=4.0, description="0.25=muito lento, 4.0=muito rapido")
    stability: float | None = Field(default=None, ge=0.0, le=1.0, description="0=mais variacao, 1=mais estavel")
    similarity_boost: float | None = Field(default=None, ge=0.0, le=1.0, description="0=menos fiel, 1=mais fiel a voz original")
    style: float | None = Field(default=None, ge=0.0, le=1.0, description="Exagero de expressao (0=desligado, 1=max)")
    speaker_boost: bool | None = Field(default=None, description="Pos-processamento de clareza")
    language_code: str | None = Field(default=None, description="Forca pronuncia (ISO 639-1, ex: 'pt', 'en')")
    output_format: str | None = Field(default=None, description="Formato do audio (ex: 'mp3_44100_128', 'opus_48000_128')")


class TTSResponse(BaseModel):
    url: str
    filename: str


@router.post("/", response_model=TTSResponse)
async def generate_tts(body: TTSRequest):
    tts = ElevenLabsClient()
    audio = await tts.generate(
        body.text,
        voice_id=body.voice_id,
        speed=body.speed,
        stability=body.stability,
        similarity_boost=body.similarity_boost,
        style=body.style,
        speaker_boost=body.speaker_boost,
        language_code=body.language_code,
        output_format=body.output_format,
    )
    filename = tts.audio_filename()
    save_media("audio", filename, audio)

    return TTSResponse(url=media_url("audio", filename), filename=filename)
