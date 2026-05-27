"""
Cliente ElevenLabs — text-to-speech via SDK oficial.
Usa AsyncElevenLabs + VoiceSettings.
"""

import uuid

from elevenlabs import VoiceSettings
from elevenlabs.client import AsyncElevenLabs

from app.config import get_settings
from app.utils.logging import get_logger

log = get_logger(__name__)


class ElevenLabsClient:
    """Cliente para ElevenLabs TTS via SDK oficial."""

    def __init__(self) -> None:
        settings = get_settings()
        self._client = AsyncElevenLabs(api_key=settings.elevenlabs_api_key)
        self._voice_id = settings.elevenlabs_voice_id
        self._model_id = settings.elevenlabs_model_id
        self._output_format = settings.elevenlabs_output_format
        self._stability = settings.elevenlabs_stability
        self._similarity_boost = settings.elevenlabs_similarity_boost
        self._speed = settings.elevenlabs_speed
        self._style = settings.elevenlabs_style
        self._speaker_boost = settings.elevenlabs_speaker_boost

    async def generate(
        self,
        text: str,
        *,
        voice_id: str | None = None,
        speed: float | None = None,
        stability: float | None = None,
        similarity_boost: float | None = None,
        style: float | None = None,
        speaker_boost: bool | None = None,
        language_code: str | None = None,
        output_format: str | None = None,
    ) -> bytes:
        """Gera audio a partir de texto. Retorna bytes de audio."""
        effective_voice_id = voice_id or self._voice_id
        voice_settings = VoiceSettings(
            stability=stability if stability is not None else self._stability,
            similarity_boost=similarity_boost
            if similarity_boost is not None
            else self._similarity_boost,
            speed=speed if speed is not None else self._speed,
            style=style if style is not None else self._style,
            use_speaker_boost=speaker_boost
            if speaker_boost is not None
            else self._speaker_boost,
        )

        chunks: list[bytes] = []
        async for chunk in self._client.text_to_speech.convert(
            voice_id=effective_voice_id,
            text=text,
            model_id=self._model_id,
            output_format=output_format or self._output_format,
            voice_settings=voice_settings,
            language_code=language_code,
        ):
            chunks.append(chunk)

        audio = b"".join(chunks)
        log.info(
            "elevenlabs.audio_generated",
            text_len=len(text),
            audio_kb=round(len(audio) / 1024, 1),
            voice=effective_voice_id,
            voice_override=voice_id is not None,
            speed=voice_settings.speed,
            stability=voice_settings.stability,
        )
        return audio

    def audio_filename(self) -> str:
        return f"{uuid.uuid4()}.mp3"
