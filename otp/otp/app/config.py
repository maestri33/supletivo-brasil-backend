"""Application config — reads .env via pydantic-settings."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Identidade ──
    service_name: str = "otp"
    env: Literal["dev", "staging", "prod"] = "dev"
    log_level: str = "INFO"
    port: int = 8000

    # ── Banco ──
    database_url: str = "postgresql+asyncpg://v7m:v7m@postgres:5432/v7m"
    database_schema: str = "otp"

    # ── Serviço notify ──
    notify_base_url: str = "http://notify:8000"
    webhook_base_url: str = "http://otp:8000"

    # ── Regras OTP ──
    otp_footer: str = ""
    otp_ttl_s: int = 300
    otp_num_digits: int = 6
    otp_max_attempts: int = 3
    otp_active: bool = True

    # ── Rate limit (por external_id) ──
    otp_ratelimit_window_s: int = 30
    otp_ratelimit_hourly_max: int = 5

    # ── Cleanup automático de logs ──
    otp_cleanup_interval_s: int = 3600
    otp_cleanup_retention_days: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()
