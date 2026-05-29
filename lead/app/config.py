"""Settings centralizada do service `lead` — pydantic-settings 2.

Carrega `.env` em runtime e expõe a instância `settings` consumida pelos
routers, notify handlers e integrações HTTP. Defaults seguros pra dev;
em produção, o docker compose injeta env vars que sobrescrevem.
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

    # ── Identidade do serviço ───────────────────────────────────────────────
    SERVICE_NAME: str = "lead"
    APP_VERSION: str = "0.3.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # ── Banco ───────────────────────────────────────────────────────────────
    DATABASE_URL: str
    DATABASE_SCHEMA: str = "lead"

    # ── Integrações com outros microsserviços v7m ───────────────────────────
    INFINITEPAY_BASE_URL: str
    ASAAS_BASE_URL: str = "http://asaas:8000"
    AUTH_BASE_URL: str
    JWT_BASE_URL: str
    NOTIFY_BASE_URL: str
    PROFILES_BASE_URL: str
    HTTP_TIMEOUT: int = Field(default=10, ge=1)

    # ── Regras de negócio ───────────────────────────────────────────────────
    PROMOTER_DEFAULT: str
    # URL publica do lead — usada para montar absolute URLs nos templates
    # de mensagem (ex.: QR PNG do PIX). Em dev: http://localhost:8137.
    # Em prod: hostname publico HTTPS (ex.: https://lead.v7m.example).
    LEAD_PUBLIC_BASE_URL: str = "http://localhost:8137"
    # Default de cobranca PIX em REAIS (NAO centavos — Asaas opera em reais).
    # ATENCAO: Asaas em PRODUCAO exige minimo R$ 5,00 (rejeita com
    # `asaas_charge_create_failed` em valores menores). Sandbox aceita qualquer.
    PIX_DEFAULT_AMOUNT: float = Field(default=999.99, gt=0)
    PIX_DEFAULT_DESCRIPTION: str = "Matrícula Supletivo: Material didático..."
    # Vencimento default da cobranca PIX (dias a partir de hoje).
    # None => deixa o asaas resolver via ASAAS_APP_CHARGE_DEFAULT_DUE_DAYS.
    PIX_DEFAULT_DUE_DAYS: int | None = None
    # Diretorio onde QR PNGs sao salvos. Mounted via volume lead_media.
    MEDIA_DIR: str = "/app/media"

    # ── Polling notify_lead_captured ────────────────────────────────────────
    # Tempo total (segundos) que esperamos o auth.provision criar o contact
    # no notify antes de marcar a mensagem de boas-vindas como skipped.
    LEAD_CONTACT_POLL_TIMEOUT_S: int = Field(default=60, ge=2)
    LEAD_CONTACT_POLL_INTERVAL_S: int = Field(default=2, ge=1)

    # ── Webhooks de saída ───────────────────────────────────────────────────
    WEBHOOK_ENROLLMENT_URL: str = ""
    WEBHOOK_PROMOTERS_URL: str = ""

    # ── Callback URL que o notify usa para reportar status da entrega ──────
    # Notify vai POSTar em {NOTIFY_CALLBACK_URL}/{message_id} ao final do
    # processamento. URL precisa ser alcançável pelo notify — dentro da
    # network do docker, usar o nome do servico (`http://lead:8000/...`).
    # Sem este callback, o lead nao sabe se a mensagem chegou no destino:
    # apenas registra `sent` apos POST 2xx, sem confirmar entrega real.
    NOTIFY_CALLBACK_URL: str = "http://lead:8000/api/v1/webhook/notify"

    # ── CORS ────────────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = ["*"]


settings = Settings()
