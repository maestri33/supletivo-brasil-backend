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
    deepseek_default_temperature: float = 0.3
    deepseek_max_tokens: int = (
        0  # 0 = nao envia max_tokens (API decide). Defina um valor para limitar.
    )

    # ElevenLabs TTS
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "JBFqnCBsd6RMkjVDRZzb"
    elevenlabs_model_id: str = "eleven_v3"
    elevenlabs_output_format: str = "mp3_44100_128"
    elevenlabs_stability: float = (
        0.5  # 0-1, consistencia na entrega (maior = mais estavel)
    )
    elevenlabs_similarity_boost: float = 0.75  # 0-1, fidelidade ao sample original
    elevenlabs_speed: float = 1.0  # 0.25-4.0, velocidade de playback
    elevenlabs_style: float = 0.0  # 0-1, exagera caracteristicas da voz (0=desligado)
    elevenlabs_speaker_boost: bool = True  # pos-processamento de clareza

    # Gemini (geracao de imagens + visao)
    gemini_api_key: str = ""
    gemini_image_model: str = "gemini-3.1-flash-image-preview"
    gemini_vision_model: str = "gemini-3-flash-preview"

    # Google Cloud Vision (OCR)
    google_vision_api_key: str = ""
    google_vision_service_account_json: str = ""  # path to service account JSON file

    # URL publica deste servico
    public_base_url: str = "https://ai.m33.live"

    # Database
    database_url: str = "postgresql+asyncpg://v7m:v7m@postgres:5432/v7m"
    database_schema: str = "ai"


@lru_cache
def get_settings() -> Settings:
    return Settings()
