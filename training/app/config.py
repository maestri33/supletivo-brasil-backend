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

    # URLs internas dos demais servicos. Defaults seguem nomes do docker-compose
    # (rede interna do Proxmox/Docker); .env real sobrescreve.
    ai_base_url: str = "http://ai:8000"
    roles_base_url: str = "http://roles:8000"
    notify_base_url: str = "http://notify:8000"
    jwt_base_url: str = "http://jwt:8000"

    # Timeouts (segundos). IA recebe um timeout maior porque LLM e' lento.
    http_timeout: int = Field(default=10, ge=1)
    ai_timeout: int = Field(default=60, ge=1)

    # Papeis usados pelos gates de autenticacao. Mantidos em settings para
    # nao espalhar magic strings — alinha com a lista do servico `roles`.
    role_trainee: str = "training"
    role_coordinator: str = "coordinator"
    role_promoted_target: str = "promoter"

    # Nota minima para considerar materia aprovada (TODO: ">= 6").
    grade_pass_threshold: float = Field(default=6.0, ge=0.0, le=10.0)

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
