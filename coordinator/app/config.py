"""Config do coordinator-service."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    service_name: str = "coordinator-service"
    version: str = "0.1.0"
    env: str = "dev"
    log_level: str = "INFO"
    port: int = 8015
    host: str = "0.0.0.0"
    database_url: str = "postgresql+asyncpg://v7m:v7m@postgres:5432/v7m"
    database_schema: str = "coordinator"
    # ── Integrations ──
    commissions_service_url: str = "http://commissions:8014"
    roles_service_url: str = "http://roles:8000"
    hub_service_url: str = "http://hub:8000"
    coordinator_commission_cents: int = 50


@lru_cache
def get_settings() -> Settings:
    return Settings()
