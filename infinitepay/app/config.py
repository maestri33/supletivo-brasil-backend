"""Configuracao do servico — leitura do .env via pydantic-settings.

Tudo que vem de fora (URL de banco, secrets, config da loja) passa por aqui.
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

    # Banco — Postgres central v7m com schema infinitepay
    database_url: str = "postgresql+asyncpg://v7m:v7m@postgres:5432/v7m"
    database_schema: str = "infinitepay"

    # InfinitePay API externa
    infinitepay_base_url: str = "https://api.checkout.infinitepay.io"
    http_timeout: float = 15.0
    worker_poll_seconds: float = 5.0
    run_inline_worker: bool = True

    # Fernet key p/ cifrar o external_id no webhook_url (rota publica)
    webhook_encryption_key: str = ""

    # Seguranca de webhook — HMAC secret + IP allow-list
    infinitepay_webhook_secret: str | None = Field(
        default=None, validation_alias="INFINITEPAY_WEBHOOK_SECRET"
    )
    infinitepay_webhook_allowed_cidrs: str | None = Field(
        default=None, validation_alias="INFINITEPAY_WEBHOOK_ALLOWED_CIDRS"
    )

    # ── Config da loja (antes na tabela `config`; agora 100% via .env) ─────────
    # Defaults usados quando o body do POST /checkout nao informa o campo.
    handle: str | None = Field(default=None, validation_alias="INFINITEPAY_HANDLE")
    price: int | None = Field(default=None, validation_alias="INFINITEPAY_PRICE")
    quantity: int = Field(default=1, validation_alias="INFINITEPAY_QUANTITY")
    description: str | None = Field(default=None, validation_alias="INFINITEPAY_DESCRIPTION")
    redirect_url: str | None = Field(default=None, validation_alias="INFINITEPAY_REDIRECT_URL")
    backend_webhook: str | None = Field(
        default=None, validation_alias="INFINITEPAY_BACKEND_WEBHOOK"
    )
    public_api_url: str | None = Field(default=None, validation_alias="INFINITEPAY_PUBLIC_API_URL")

    # ── Integracao com o app `ai` central (usado por receipt + monitor) ────────
    # receipt/monitor chamam o app `ai` em {ai_base_url}/api/v1/text/chat — nunca
    # a DeepSeek direto (§12: 1 integracao externa = 1 app dono). Sem essa
    # integracao o fluxo de checkout continua funcionando (fallbacks).
    ai_base_url: str = "http://ai:8000"
    ai_features_enabled: bool = Field(default=False, validation_alias="AI_FEATURES_ENABLED")
    ai_model: str = "deepseek-v4-flash"  # triagem rapida / mensagem de recibo
    ai_pro_model: str = "deepseek-v4-pro"  # analise profunda de anomalia


@lru_cache
def get_settings() -> Settings:
    """Settings singleton — uma instancia por processo."""
    return Settings()
