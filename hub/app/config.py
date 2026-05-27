"""Configuracao do servico hub."""

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

    # ── Identidade ───────────────────────────────────────────────
    service_name: str = "hub"
    env: Literal["dev", "staging", "prod"] = "dev"
    log_level: str = "INFO"

    # ── Banco ────────────────────────────────────────────────────
    database_url: str
    database_schema: str = "hub"

    # ── Auth (JWT via servico auth/jwt) ──────────────────────────
    jwt_base_url: str = ""
    staff_roles: list[str] = ["admin", "staff"]

    # ── HTTP ─────────────────────────────────────────────────────
    http_timeout: int = Field(default=10, ge=1)
    cors_origins: list[str] = ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
