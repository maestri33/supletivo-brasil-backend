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

    # ── Comissoes (VALORES = CONFIG: referencia do dono; baixar no .env p/ teste) ──
    promoter_commission_cents: int = 10000   # R$100 por lead que PAGA (ao promotor que indicou)
    coordinator_commission_cents: int = 5000  # R$50 por aluno que vira veteran (ao coordenador do hub)
    bonus_threshold_count: int = 5            # >=5 indicacoes que pagaram na semana -> bonus
    bonus_flat_cents: int = 50000             # R$500 FLAT: nao escala (5 ou 100 indicacoes ganham o mesmo)
    processing_cron_hour: int = 18            # sexta-feira as 18h America/Sao_Paulo
    processing_cron_timezone: str = "America/Sao_Paulo"

    # ── Asaas (internal service, CONVENTION §12) ─────────────────
    asaas_base_url: str = "http://asaas:8000"
    http_timeout: float = 30.0                # timeout das chamadas HTTP ao asaas
    payout_poll_seconds: int = 60             # frequencia do worker que empurra/reconcilia payouts

    # ── Webhook ──────────────────────────────────────────────────
    commissions_webhook_token: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
