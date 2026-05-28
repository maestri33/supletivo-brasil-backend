"""Configuração do serviço enrollment.

Tudo que vem de fora (URL de banco, URLs internas dos demais apps) passa por
aqui. Defaults apontam para os service names do docker-compose; o `.env` real
sobrescreve via `pydantic-settings`.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    service_name: str = "enrollment"
    env: Literal["dev", "staging", "prod"] = "dev"
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://v7m:v7m@postgres:5432/v7m"
    database_schema: str = "enrollment"

    # URLs internas dos serviços que o enrollment consome (CONVENTION §7).
    # Defaults batem com os nomes de serviço no docker-compose.dev.yml; o .env
    # real sobrescreve.
    ai_base_url: str = "http://ai:8000"
    notify_base_url: str = "http://notify:8000"
    documents_base_url: str = "http://documents:8000"
    addresses_base_url: str = "http://address:8000"
    profiles_base_url: str = "http://profiles:8000"
    roles_base_url: str = "http://roles:8000"
    jwt_base_url: str = "http://jwt:8000"

    http_timeout: int = Field(default=10, ge=1)


@lru_cache
def get_settings() -> Settings:
    return Settings()
