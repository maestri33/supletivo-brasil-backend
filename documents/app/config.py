"""Configuracao do servico — leitura do .env via pydantic-settings.

Tudo que vem de fora (URL de banco, URLs internas) passa por aqui.
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

    # Banco — Postgres central com schema proprio `documents`.
    # Sem default: credencial de banco nunca fica hardcoded.
    database_url: str
    database_schema: str = "documents"

    # URLs internas — defaults apontam para nomes de servico no docker-compose.
    auth_base_url: str = "http://auth:8000"
    notify_base_url: str = "http://notify:8000"

    # Upload
    media_root: str = "/root/media"
    max_upload_mb: int = 10

    # Webhook
    webhook_url: str = "http://10.10.10.129"

    # Ambiente / observabilidade
    service_name: str = "documents-service"
    app_version: str = "1.0.0"
    environment: str = "development"
    debug: bool = False
    log_level: str = "INFO"
    port: int = 80


@lru_cache
def get_settings() -> Settings:
    """Settings singleton — uma instancia por processo."""
    return Settings()


settings = get_settings()
