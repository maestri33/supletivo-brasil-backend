"""
Configuracao do servico — leitura do .env via pydantic-settings.

Tudo que vem de fora (URL de banco, secrets) passa por aqui.
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

    # Banco — Postgres central v7m com schema asaas
    database_url: str
    database_schema: str = "asaas"

    # Asaas — production-only por padrao; habilita sandbox via env
    asaas_base_url: str = "https://api.asaas.com"
    # Quando True, aceita chaves $aact_hmlg_ (sandbox) alem de $aact_prod_
    asaas_allow_sandbox: bool = Field(default=False, validation_alias="ASAAS_ALLOW_SANDBOX")

    # ── Bootstrap config via .env ─────────────────────────────────────────────
    # Pos-wipe (ou primeiro deploy), _seed_from_env() popula asaas.config se
    # a tabela esta vazia. Se ja tem entry, o DB vence (operador pode override
    # via POST /api/v1/config/*). Padrao alinhado com como Mailcow funciona.
    asaas_api_key: str | None = Field(default=None, validation_alias="ASAAS_API_KEY")
    asaas_external_url: str | None = Field(default=None, validation_alias="ASAAS_EXTERNAL_URL")
    asaas_wallet_id: str | None = Field(default=None, validation_alias="ASAAS_WALLET_ID")
    asaas_internal_url: str | None = Field(default=None, validation_alias="ASAAS_INTERNAL_URL")
    asaas_internal_url_charge: str | None = Field(
        default=None, validation_alias="ASAAS_INTERNAL_URL_CHARGE"
    )
    asaas_internal_url_payout: str | None = Field(
        default=None, validation_alias="ASAAS_INTERNAL_URL_PAYOUT"
    )
    asaas_internal_url_scheduling: str | None = Field(
        default=None, validation_alias="ASAAS_INTERNAL_URL_SCHEDULING"
    )

    # Webhook HMAC secret — mesma chave configurada no painel Asaas
    asaas_webhook_secret: str | None = Field(default=None, validation_alias="ASAAS_WEBHOOK_SECRET")

    # Nonce TTL for external URL verification
    url_verify_nonce_ttl: int = 600

    # Default scheduled payment hour (America/Sao_Paulo)
    default_scheduled_hour: int = 8

    # Webhook — managed by the app
    webhook_name: str = "asaas-app-managed"

    # Default due date offset (days) when creating charges sem due_date explicito
    charge_default_due_days: int = 3


# Application constants — nao sao env-driven
WEBHOOK_EVENTS = [
    # Outbound (TRANSFER_*)
    "TRANSFER_CREATED",
    "TRANSFER_PENDING",
    "TRANSFER_IN_BANK_PROCESSING",
    "TRANSFER_DONE",
    "TRANSFER_FAILED",
    "TRANSFER_CANCELLED",
    "TRANSFER_BLOCKED",
    # Inbound charges (PAYMENT_*)
    "PAYMENT_CREATED",
    "PAYMENT_AWAITING_RISK_ANALYSIS",
    "PAYMENT_APPROVED_BY_RISK_ANALYSIS",
    "PAYMENT_REPROVED_BY_RISK_ANALYSIS",
    "PAYMENT_UPDATED",
    "PAYMENT_CONFIRMED",
    "PAYMENT_RECEIVED",
    "PAYMENT_OVERDUE",
    "PAYMENT_DELETED",
    "PAYMENT_RESTORED",
    "PAYMENT_REFUNDED",
    "PAYMENT_RECEIVED_IN_CASH_UNDONE",
    "PAYMENT_CHARGEBACK_REQUESTED",
    "PAYMENT_CHARGEBACK_DISPUTE",
    "PAYMENT_AWAITING_CHARGEBACK_REVERSAL",
    "PAYMENT_DUNNING_RECEIVED",
    "PAYMENT_DUNNING_REQUESTED",
    "PAYMENT_BANK_SLIP_VIEWED",
    "PAYMENT_CHECKOUT_VIEWED",
]


@lru_cache
def get_settings() -> Settings:
    """Settings singleton — uma instancia por processo."""
    return Settings()
