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

    # Banco — Postgres central com schema proprio `candidate`.
    # Sem default: credencial de banco nunca fica hardcoded (CONVENTION Fase 1).
    database_url: str = Field(validation_alias="CANDIDATE_APP_DB_URL")
    database_schema: str = "candidate"

    # URLs internas dos demais servicos (HTTP). Defaults apontam para os nomes
    # de servico no docker-compose; o .env real sobrescreve.
    auth_base_url: str = "http://auth:8000"
    jwt_base_url: str = "http://jwt:8000"
    notify_base_url: str = "http://notify:8000"
    profiles_base_url: str = "http://profiles:8000"
    addresses_base_url: str = "http://addresses:8000"
    roles_base_url: str = "http://roles:8000"
    asaas_base_url: str = "http://asaas:8000"
    documents_base_url: str = "http://documents:8000"
    ai_base_url: str = "http://ai:8000"

    # Negocio — hub padrao quando o cadastro nao informa um hub explicito.
    hub_default: str = "00000000-0000-0000-0000-000000000000"

    # HTTP
    http_timeout: int = Field(default=10, ge=1)

    # Ambiente / observabilidade
    service_name: str = "candidate"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = False
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Settings singleton — uma instancia por processo."""
    return Settings()
