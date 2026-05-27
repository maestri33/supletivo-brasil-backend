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

    # Banco — Postgres central com schema proprio `promoter`.
    # Sem default: credencial de banco nunca fica hardcoded (CONVENTION Fase 1).
    database_url: str = Field(validation_alias="PROMOTER_APP_DB_URL")
    database_schema: str = "promoter"

    # URLs internas dos demais servicos (HTTP). Defaults apontam para os nomes
    # de servico no docker-compose; o .env real sobrescreve.
    auth_base_url: str = "http://auth:8000"
    jwt_base_url: str = "http://jwt:8000"
    notify_base_url: str = "http://notify:8000"
    profiles_base_url: str = "http://profiles:8000"
    roles_base_url: str = "http://roles:8000"
    lead_base_url: str = "http://lead:8000"
    commissions_base_url: str = "http://commissions:8000"

    # Negocio — hub padrao quando a criacao nao informa um hub explicito.
    hub_default: str = "00000000-0000-0000-0000-000000000000"
    # Base da landing page de captacao; o promoter divulga `<base>/ref=<external_id>`.
    landing_base_url: str = "https://captacao.exemplo.com"

    # HTTP
    http_timeout: int = Field(default=10, ge=1)

    # Ambiente / observabilidade
    service_name: str = "promoter"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = False
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Settings singleton — uma instancia por processo."""
    return Settings()
