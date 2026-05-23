"""
Cliente para ElevenLabs Text-to-Speech.

Usa o SDK oficial elevenlabs (modelo eleven_v3).
O SDK e sincrono — todas as chamadas publicas rodam em thread via anyio.
"""

from __future__ import annotations

import uuid
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

import anyio

from app.config import get_settings
from app.utils.logging import get_logger

if TYPE_CHECKING:
    from elevenlabs.client import ElevenLabs

log = get_logger(__name__)

# Lazy import — o SDK faz chamadas de rede no __init__
_elevenlabs: ElevenLabs | None = None


def _get_client() -> ElevenLabs:
    global _elevenlabs
    if _elevenlabs is None:
        from elevenlabs.client import ElevenLabs

        _elevenlabs = ElevenLabs(api_key=get_settings().elevenlabs_api_key)
    return _elevenlabs


def _convert_sync(text: str, voice_id: str, model_id: str, output_format: str) -> bytes:
    """Conversao TTS sincrona — chamada em thread separada."""
    client = _get_client()
    audio = client.text_to_speech.convert(
        text=text,
        voice_id=voice_id,
        model_id=model_id,
        output_format=output_format,
    )
    data = b"".join(audio) if not isinstance(audio, (bytes, bytearray)) else bytes(audio)
    return data


class ElevenLabsClient:
    """Cliente para geracao de audio via ElevenLabs TTS (eleven_v3)."""

    def __init__(self) -> None:
        settings = get_settings()
        self._voice_id = settings.elevenlabs_voice_id
        self._model_id: str = settings.elevenlabs_model_id
        self._output_format: str = settings.elevenlabs_output_format

    async def text_to_speech(self, text: str) -> bytes:
        """Converte texto em audio (bytes MP3). Executa SDK sync em thread."""
        data = await anyio.to_thread.run_sync(
            partial(
                _convert_sync,
                text,
                self._voice_id,
                self._model_id,
                self._output_format,
            )
        )
        log.info("elevenlabs.tts_generated", chars=len(text), bytes=len(data))
        return data

    async def generate_and_save(self, text: str, output_dir: str = "media/audio") -> str:
        """Gera audio e salva em disco. Retorna o path relativo (p/ URL publica)."""
        data = await self.text_to_speech(text)

        def _save() -> str:
            out = Path(output_dir)
            out.mkdir(parents=True, exist_ok=True)
            filename = f"{uuid.uuid4().hex}.mp3"
            path = out / filename
            path.write_bytes(data)
            relative = f"{out.name}/{filename}"
            return relative

        relative = await anyio.to_thread.run_sync(_save)
        log.info("elevenlabs.audio_saved", relative=relative)
        return relative
