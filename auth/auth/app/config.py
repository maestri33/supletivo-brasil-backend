"""Configuracoes da aplicacao via pydantic-settings."""

from enum import StrEnum
from functools import lru_cache

from pydantic_settings import BaseSettings


class Environment(StrEnum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    DATABASE_URL: str = "sqlite+aiosqlite:///auth.db"
    DB_SCHEMA: str = "auth"
    REDIS_URL: str = "redis://localhost:6379/0"
    ENVIRONMENT: Environment = Environment.DEVELOPMENT
    APP_VERSION: str = "0.3.0"
    CORS_ORIGINS: list[str] = ["*"]

    # Downstream services
    PROFILES_SERVICE_URL: str = ""
    OTP_SERVICE_URL: str = ""
    JWT_SERVICE_URL: str = ""
    ROLES_SERVICE_URL: str = ""
    NOTIFY_SERVICE_URL: str = ""
    LEAD_SERVICE_URL: str = ""


@lru_cache
def get_settings() -> Settings:
    """Retorna instancia cacheada das configuracoes."""
    return Settings()
