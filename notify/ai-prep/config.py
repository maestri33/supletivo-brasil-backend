"""
Configuracao do servico AI — leitura do .env via pydantic-settings.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Identificacao do servico
    service_name: str = "ai"
    env: Literal["dev", "staging", "prod"] = "dev"
    log_level: str = "INFO"
    port: int = 80

    # DeepSeek (geracao de texto + JSON estruturado)
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_default_model: str = "deepseek-v4-pro"
    deepseek_flash_model: str = "deepseek-v4-flash"
    deepseek_default_temperature: float = 0.3

    # ElevenLabs TTS
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "JBFqnCBsd6RMkjVDRZzb"
    elevenlabs_model_id: str = "eleven_v3"
    elevenlabs_output_format: str = "mp3_44100_128"

    # Gemini (geracao de imagens + visao)
    gemini_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/models"
    gemini_image_model: str = "gemini-3.1-flash-image-preview"
    gemini_vision_model: str = "gemini-3-flash-preview"

    # URL publica deste servico
    public_base_url: str = "https://ai.v7m.live"

    # URL interna na DMZ
    dmz_base_url: str = "http://ai.local:80"


@lru_cache
def get_settings() -> Settings:
    return Settings()
