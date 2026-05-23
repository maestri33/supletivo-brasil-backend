"""Configuracao centralizada — tudo que varia por ambiente sai do .env."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.services.key_service import generate_rsa_key_pair
from app.utils.logging import get_logger

log = get_logger(__name__)


class Settings(BaseSettings):
    """Cada atributo = uma env var. Sem defaults escondidos."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -- Servico --
    service_name: str = "jwt"
    env: Literal["dev", "staging", "prod"] = "dev"
    log_level: str = "INFO"
    port: int = 8000

    # -- JWT --
    jwt_algorithm: str = "RS256"
    jwt_access_expire_minutes: int = 30
    jwt_refresh_expire_minutes: int = 1440
    jwt_issuer: str = "jwt"
    jwt_audience: str = ""

    # -- Chaves RSA —
    jwt_private_key_file: str = "private.pem"
    jwt_public_key_file: str = "public.pem"


@lru_cache
def get_settings() -> Settings:
    """Singleton — le .env uma vez e garante que as chaves existam."""
    settings = Settings()
    _ensure_keys(settings)
    return settings


def _ensure_keys(settings: Settings) -> None:
    """Gera par RSA se os arquivos de chave nao existirem."""
    priv_path = Path(settings.jwt_private_key_file)
    pub_path = Path(settings.jwt_public_key_file)

    if priv_path.exists() and pub_path.exists():
        return

    log.info("config.gerando_chaves", alg=settings.jwt_algorithm)
    priv_pem, pub_pem = generate_rsa_key_pair()
    priv_path.write_text(priv_pem)
    pub_path.write_text(pub_pem)
    log.info("config.chaves_salvas", priv=str(priv_path), pub=str(pub_path))


def load_private_key(settings: Settings) -> str:
    return Path(settings.jwt_private_key_file).read_text()


def load_public_key(settings: Settings) -> str:
    return Path(settings.jwt_public_key_file).read_text()
