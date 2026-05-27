"""Configuração do serviço Roles."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_VALID_ROLES: list[str] = [
    "lead",
    "candidate",
    "enrollment",
    "promoter",
    "student",
    "veteran",
    "coordinator",
    "staff",
    "admin",
]


DEFAULT_ROLE_RULES: list[dict] = [
    {"from_role": None, "to_role": "lead", "mode": "add"},
    {"from_role": "lead", "to_role": "enrollment", "mode": "replace"},
    {"from_role": "enrollment", "to_role": "student", "mode": "replace"},
    {"from_role": None, "to_role": "veteran", "mode": "add", "requires_role": "student"},
    {"from_role": None, "to_role": "candidate", "mode": "add"},
    {"from_role": "candidate", "to_role": "promoter", "mode": "replace"},
    {"from_role": None, "to_role": "coordinator", "mode": "add", "requires_role": "promoter"},
]


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

    # Catálogo de roles válidas + regras de transição (§8 CONVENTION.md).
    # `.env` aceita JSON: VALID_ROLES='["lead",...]' e ROLE_RULES='[{...}]'.
    VALID_ROLES: list[str] = Field(default_factory=lambda: list(DEFAULT_VALID_ROLES))
    ROLE_RULES: list[dict] = Field(default_factory=lambda: list(DEFAULT_ROLE_RULES))


settings = Settings()
