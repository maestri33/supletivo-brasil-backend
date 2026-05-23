from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    database_url: str = "postgresql+psycopg2://v7m:v7m@postgres:5432/v7m"
    database_schema: str = "infinitepay"

    infinitepay_base_url: str = "https://api.checkout.infinitepay.io"
    http_timeout: float = 15.0
    worker_poll_seconds: float = 5.0
    run_inline_worker: bool = True

    webhook_encryption_key: str = ""

    # ── Bootstrap config via .env ─────────────────────────────────────────────
    # Pos-wipe, _seed_from_env() popula a tabela infinitepay.config (row id=1)
    # com esses valores se eles vierem do .env. DB vence se ja tem entry
    # (operador pode override via PATCH /api/v1/config). Mesmo padrao do
    # Asaas/Mailcow.
    infinitepay_handle: str | None = Field(default=None, validation_alias="INFINITEPAY_HANDLE")
    infinitepay_price: int | None = Field(default=None, validation_alias="INFINITEPAY_PRICE")
    infinitepay_quantity: int | None = Field(default=None, validation_alias="INFINITEPAY_QUANTITY")
    infinitepay_description: str | None = Field(default=None, validation_alias="INFINITEPAY_DESCRIPTION")
    infinitepay_redirect_url: str | None = Field(default=None, validation_alias="INFINITEPAY_REDIRECT_URL")
    infinitepay_backend_webhook: str | None = Field(default=None, validation_alias="INFINITEPAY_BACKEND_WEBHOOK")
    infinitepay_public_api_url: str | None = Field(default=None, validation_alias="INFINITEPAY_PUBLIC_API_URL")

    # AI service v7m (usado por receipt + monitor, sem tool_calling).
    # analytics + reporter ainda chamam DeepSeek direto via OpenAI client
    # porque dependem de tool_calling com DB local — ver app/ai/client.py.
    ai_base_url: str = "http://ai:8000"

    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-v4-flash"
    deepseek_pro_model: str = "deepseek-v4-pro"
    deepseek_ai_features_enabled: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
