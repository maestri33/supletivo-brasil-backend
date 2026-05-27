"""
Configuracao do servico student — leitura do .env via pydantic-settings.

Tudo que vem de fora (URLs de servicos, timeout, etc.) passa por aqui.
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

    # ── Banco ──
    database_url: str
    database_schema: str = "student"

    # ── Identidade ──
    service_name: str = "student"
    app_version: str = "0.1.0"

    # ── JWT (JWKS no servico jwt) ──
    jwt_base_url: str = Field(validation_alias="JWT_BASE_URL")

    # ── CORS ──
    cors_origins: list[str] = []

    # ── Integracoes internas (CONVENTION §7) ──
    ai_base_url: str = "http://ai:80"
    documents_base_url: str = "http://documents:8000"
    notify_base_url: str = "http://notify:8000"
    commissions_base_url: str = "http://commissions:8000"
    roles_base_url: str = "http://roles:8000"
    profiles_base_url: str = "http://profiles:8000"

    # Timeout padrao de cada client httpx (segundos).
    http_timeout: float = 10.0

    # Valor da comissao do coordenador na formatura (em centavos).
    coordinator_commission_cents: int = 50


@lru_cache
def get_settings() -> Settings:
    """Settings singleton — uma instancia por processo."""
    return Settings()
