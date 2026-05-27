"""Configuração do serviço hub."""

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

    service_name: str = "hub"
    env: Literal["dev", "staging", "prod"] = "dev"
    log_level: str = "INFO"

    # Obrigatório (sem default inseguro): vem do .env — mesmo padrão de otp/asaas (Fase 1).
    database_url: str
    database_schema: str = "hub"


@lru_cache
def get_settings() -> Settings:
    return Settings()
