"""Config do commissions-service."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    service_name: str = "commissions-service"
    version: str = "0.1.0"
    env: str = "dev"
    log_level: str = "INFO"
    port: int = 8014
    host: str = "0.0.0.0"

    database_url: str = "postgresql+asyncpg://v7m:v7m@postgres:5432/v7m"
    database_schema: str = "commissions"

    # ── Comissoes ────────────────────────────────────────────────
    promoter_commission_cents: int = 100  # R$ 1,00 por lead completo
    coordinator_commission_cents: int = 50  # R$ 0,50 por aluno formado
    bonus_threshold_count: int = 10  # minimo de leads p/ bonus
    bonus_comission_cents: int = 50  # R$ 0,50 bonus por lead acima do threshold
    processing_cron_hour: int = 18  # sexta-feira as 18h America/Sao_Paulo
    processing_cron_timezone: str = "America/Sao_Paulo"

    # ── Asaas ────────────────────────────────────────────────────
    asaas_base_url: str = "https://api-sandbox.asaas.com"
    asaas_api_key: str = ""

    # ── Webhook ──────────────────────────────────────────────────
    commissions_webhook_token: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
