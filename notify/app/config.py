"""
Configuracao do servico — leitura do .env via pydantic-settings.

Tudo que vier de fora (URL de banco, broker, redis, secrets) passa por aqui.
Nao leia env var direto fora deste modulo.
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

    # Identificacao do servico
    service_name: str = "notify"
    env: Literal["dev", "staging", "prod"] = "dev"
    log_level: str = "INFO"
    port: int = 8000

    # Banco — Postgres central v7m, schema notify
    database_url: str = "postgresql+asyncpg://v7m:v7m@postgres:5432/v7m"
    database_schema: str = "notify"

    # Envio de email: SMTP direto STARTTLS na porta 587 + API admin Mailcow
    # opcional (gerenciar app-passwords/mailboxes). Sem default de host/url —
    # dados de infra vêm do .env (§12 da convenção); ver .env.example.
    mailcow_smtp_host: str = ""  # ex: mail.v7m.org
    mailcow_smtp_port: int = 587
    mailcow_smtp_user: str = ""  # ex: noreply@v7m.org
    mailcow_smtp_pass: str = ""  # app-password (Mailcow API admin)
    mailcow_from_email: str = ""  # default: mailcow_smtp_user
    mailcow_from_name: str = ""  # default: service_name
    mailcow_timeout_s: int = 30
    mailcow_api_url: str = ""  # ex: https://mail.v7m.org
    mailcow_api_key: str = ""

    # Envio de email via SSH + sendmail no host do Mailcow (preserva DKIM/SPF/DMARC).
    # Substitui o caminho SMTP direto (mailcow_smtp_*) quando mailcow_ssh_host preenchido.
    mailcow_ssh_host: str = ""  # ex: root@10.1.30.150
    mailcow_ssh_key: str = "/root/.ssh/id_ed25519"  # caminho da private key DENTRO do container
    mailcow_postfix_container: str = "mailcowdockerized-postfix-mailcow-1"

    # WhatsApp API (Evolution GO / whatsmeow)
    whatsapp_api_base_url: str = "http://whats-api:8080"
    whatsapp_global_api_key: str = ""
    whatsapp_instance_name: str = "default"
    # Retry para envios WhatsApp em caso de erro transitorio (5xx, timeout).
    # 0 = sem retry (comportamento legado). Cada tentativa espera
    # backoff_base_s * 2^(n-1) segundos: 1s, 3s, 9s, 27s (default cap em 3).
    whatsapp_max_retries: int = 3
    whatsapp_retry_backoff_base_s: float = 1.0

    # Vozes por genero — resolvidas via profiles.gender (M/F) antes de chamar AI /tts.
    # Quando profile nao tem gender ou lookup falha, AI usa default do provider.
    elevenlabs_voice_male: str = "RGymW84CSmfVugnA5tvA"
    elevenlabs_voice_female: str = "Zk0wRqIFBWGMu2lIk7hw"

    # AI Service
    ai_base_url: str = "http://ai:8000"

    # Mapeamento publica → LAN para URLs de midia.
    # Email usa `ai_public_base` (Gmail/cliente externo acessa via Cloudflare/Traefik).
    # WhatsApp usa `ai_lan_base` (Evolution acessa direto na sub-rede, sem TLS/DNS).
    # Ao subir novo service que sirva midia, registrar par aqui.
    ai_public_base: str = "https://api.m33.live/ai"
    ai_lan_base: str = "http://10.1.20.30:8002"
    notify_public_base: str = "https://api.m33.live/notify"
    notify_lan_base: str = "http://10.1.20.30:8015"

    # Profiles service (lookup de gender pra escolha de voz TTS)
    profiles_base_url: str = "http://profiles:8000"
    profiles_timeout_s: float = 5.0


@lru_cache
def get_settings() -> Settings:
    """Settings singleton — uma instancia por processo."""
    return Settings()
