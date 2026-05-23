from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # Services
    INFINITEPAY_BASE_URL: str
    AUTH_BASE_URL: str
    JWT_BASE_URL: str
    NOTIFY_BASE_URL: str
    PROFILES_BASE_URL: str
    ROLES_BASE_URL: str
    ADDRESSES_BASE_URL: str

    # Business
    HUB_DEFAULT: str = Field(
        description="UUID do hub padrao para fallback",
    )

    # HTTP
    HTTP_TIMEOUT: int = Field(default=10, ge=1)

    # Outbound webhooks
    WEBHOOK_ENROLLMENT_URL: str = ""
    WEBHOOK_HUB_URL: str = ""

    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = False


settings = Settings()
