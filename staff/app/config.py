"""Settings centralizada do servico `staff` — pydantic-settings 2.

Carrega `.env` em runtime. Defaults seguros pra dev;
em producao, o docker compose injeta env vars que sobrescrevem.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # ── Identidade do servico ───────────────────────────────────────────────
    SERVICE_NAME: str = "staff"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # ── Banco ───────────────────────────────────────────────────────────────
    DATABASE_URL: str
    DATABASE_SCHEMA: str = "staff"

    # ── Auth (JWT via servico jwt) ──────────────────────────────────────────
    JWT_BASE_URL: str
    STAFF_ROLES: list[str] = ["admin", "staff"]

    # ── HTTP ────────────────────────────────────────────────────────────────
    HTTP_TIMEOUT: int = Field(default=10, ge=1)
    CORS_ORIGINS: list[str] = ["*"]

    # ── Servicos dependentes (URLs internas Docker) ─────────────────────────
    HUB_BASE_URL: str = "http://hub:8000"


def get_settings() -> Settings:
    return Settings()
