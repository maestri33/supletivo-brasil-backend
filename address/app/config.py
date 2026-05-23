"""Configuração do addresses."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    service_name: str = "addresses-service"
    version: str = "1.0.0"
    env: str = "dev"
    log_level: str = "INFO"
    port: int = 8000

    database_url: str = "postgresql+asyncpg://v7m:v7m@postgres:5432/v7m"
    database_schema: str = "addresses"

    cors_origins: str = "*"

    # ViaCEP — integração implementada (ver app/integrations/viacep.py).
    viacep_base_url: str = "https://viacep.com.br"
    viacep_timeout_seconds: float = 5.0

    # Webhook — disparado em create/update/delete de Address (best-effort).
    webhook_url: str = "http://10.10.10.129"
    webhook_timeout_seconds: float = 5.0

    # Upload de comprovante (proof) das entity_addresses.
    upload_dir: str = "uploads"


@lru_cache
def get_settings() -> Settings:
    return Settings()
