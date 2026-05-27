"""Configuracao do servico — leitura do .env via pydantic-settings.

Tudo que vem de fora (URL de banco, diretorio de midia) passa por aqui.
Nao leia env var direto fora deste modulo; use get_settings().
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Banco — Postgres central com schema proprio `training`.
    # Sem default: credencial de banco nunca fica hardcoded (CONVENTION Fase 1).
    database_url: str
    database_schema: str = "training"

    # Midia das materias (video/foto) armazenada no proprio training.
    media_dir: str = "/app/media"
    max_upload_mb: int = Field(default=200, ge=1)

    # Ambiente / observabilidade
    service_name: str = "training"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = False
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Settings singleton — uma instancia por processo."""
    return Settings()
