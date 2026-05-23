"""Configuração do serviço Roles."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    SERVICE_NAME: str = "roles"
    DATABASE_URL: str = "postgresql+asyncpg://v7m:v7m@postgres:5432/v7m"
    DATABASE_SCHEMA: str = "roles"
    HOST: str = "0.0.0.0"
    PORT: int = 8000


settings = Settings()
