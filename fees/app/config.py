"""Configuração do serviço `fees` — pydantic-settings 2.

Carrega o `.env` em runtime. `database_url` é **obrigatório** (sem default
com credenciais embutidas — regra de segurança da Fase 1 da CONVENTION); o
docker-compose / `.env` injeta o valor real.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Identidade do serviço ───────────────────────────────────────────────
    service_name: str = "fees"
    env: Literal["dev", "staging", "prod"] = "dev"
    log_level: str = "INFO"

    # ── Banco ───────────────────────────────────────────────────────────────
    # Obrigatório: sem default com credenciais (CONVENTION Fase 1 / segurança).
    database_url: str
    database_schema: str = "fees"

    # ── Integrações com outros microsserviços v7m ───────────────────────────
    # asaas é o único dono da integração Asaas/PIX (§12); fees fala com ele.
    asaas_base_url: str = "http://asaas:8000"
    notify_base_url: str = "http://notify:8000"
    jwt_base_url: str = "http://jwt:8000"
    http_timeout: int = 10

    # ── Autorização ─────────────────────────────────────────────────────────
    # Nome da role exigida no gate dos endpoints autenticados. Override via
    # `.env`. A LISTA mestra de roles válidas (§8) vive no `.env` do app
    # `roles` — fees só consulta `roles` via HTTP para validar se o usuário
    # tem esta role agora.
    coordinator_role: str = "coordinator"

    # ── Regras de negócio ───────────────────────────────────────────────────
    fee_description_default: str = "Taxa de matrícula"


@lru_cache
def get_settings() -> Settings:
    return Settings()
