"""
Configuracao do servico student — leitura do .env via pydantic-settings.

Tudo que vem de fora (URL de banco, URL do jwt) passa por aqui.
Nao leia env var direto fora deste modulo.
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

    # Banco — Postgres central com schema student. Obrigatorio (sem default).
    database_url: str = Field(validation_alias="STUDENT_APP_DB_URL")
    database_schema: str = "student"

    # Identidade do servico
    service_name: str = "student"
    app_version: str = "0.1.0"

    # JWT — base URL do servico jwt (JWKS). Obrigatorio.
    jwt_base_url: str = Field(validation_alias="JWT_BASE_URL")

    # CORS — origens permitidas (lista JSON no .env)
    cors_origins: list[str] = []


@lru_cache
def get_settings() -> Settings:
    """Settings singleton — uma instancia por processo."""
    return Settings()
