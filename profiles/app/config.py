"""Configuração do profiles."""

import json
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    service_name: str = "profiles-service"
    version: str = "0.3.0"
    env: str = "dev"
    log_level: str = "INFO"
    port: int = 8000

    # Obrigatório — vem do .env (sem default; nada de credencial hardcoded).
    database_url: str
    database_schema: str = "profiles"

    cors_origins: str = "*"
    integrations: str = "{}"

    # CPFHub.io — lookup de identidade por CPF (server-side only).
    # Quando cpfhub_api_key é vazio, a integração é considerada desabilitada
    # e o profiles funciona sem enriquecimento.
    cpfhub_api_key: str = ""
    cpfhub_base_url: str = "https://api.cpfhub.io"
    cpfhub_timeout_seconds: float = 5.0

    def get_integrations(self) -> dict[str, str]:
        try:
            return json.loads(self.integrations)
        except (json.JSONDecodeError, TypeError):
            return {}


@lru_cache
def get_settings() -> Settings:
    return Settings()
