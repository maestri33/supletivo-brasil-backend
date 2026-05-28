"""Schemas de configuracao do Asaas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class SetUrlRequest(BaseModel):
    url: HttpUrl = Field(
        ...,
        description=(
            "URL publica base do asaas-app. O webhook Asaas sera registrado em <url>/webhook/."
        ),
    )

    model_config = ConfigDict(json_schema_extra={"example": {"url": "https://asaas.v7m.net/"}})


class SetUrlResponse(BaseModel):
    verify_url: HttpUrl = Field(
        ..., description="URL que deve ser acessada para confirmar o dominio"
    )
    nonce: str = Field(..., description="Token de uso unico embutido na verify_url")
    expires_in: int = Field(..., description="TTL do nonce em segundos")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "verify_url": "https://asaas.v7m.net/api/v1/config/url/verify/abc123xyz",
                "nonce": "abc123xyz",
                "expires_in": 300,
            }
        }
    )


class SetInternalUrlRequest(BaseModel):
    url: HttpUrl = Field(
        ...,
        description=(
            "URL do sistema interno que recebera copias dos eventos Asaas e eventos sinteticos."
        ),
    )
    target: str = Field(
        default="default",
        description=(
            "Categoria do evento que sera roteado a esta URL. "
            "default = catch-all (compat); scheduling = transicoes de agendamento; "
            "payout = status de payouts PIX (pixkey, qrcode); "
            "charge = status de cobrancas PIX recebidas."
        ),
        pattern="^(default|scheduling|payout|charge)$",
    )

    model_config = ConfigDict(
        json_schema_extra={"example": {"url": "http://127.0.0.1:8081/charge", "target": "charge"}}
    )


class ConfigInternalResponse(BaseModel):
    ok: bool = Field(..., description="True se o onboarding foi entregue e a URL salva")
    internal_url: str = Field(..., description="URL interna salva")
    target: str = Field(..., description="Categoria associada (default|scheduling|payout|charge)")
    onboarding_status: int = Field(
        ..., description="HTTP status code retornado pelo sistema interno"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "ok": True,
                "internal_url": "http://127.0.0.1:8081/charge",
                "target": "charge",
                "onboarding_status": 200,
            }
        }
    )


class SetKeyRequest(BaseModel):
    api_key: str = Field(
        ...,
        min_length=20,
        description="API key Asaas de producao ($aact_prod_*). Chaves sandbox sao rejeitadas.",
    )

    model_config = ConfigDict(
        json_schema_extra={"example": {"api_key": "$aact_prod_xxxxxxxxxxxxxxxxxxxxx"}}
    )


class SetKeyResponse(BaseModel):
    security_token: str = Field(..., description="Token para colar no Mecanismo de Seguranca Asaas")
    security_validator_url: HttpUrl = Field(
        ..., description="URL validadora para colar no Mecanismo de Seguranca Asaas"
    )
    webhook_endpoint: HttpUrl = Field(
        ..., description="URL que sera registrada como webhook Asaas em /api/v1/config/key/confirm"
    )
    events: list[str] = Field(..., description="Eventos Asaas assinados pelo webhook gerenciado")
    account: dict[str, Any] = Field(..., description="Resumo da conta retornado por /v3/myAccount")
    instructions_html: str = Field(
        ..., description="Instrucoes HTML prontas para exibir ao operador"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "security_token": "a1b2c3d4e5f6...",
                "security_validator_url": "https://asaas.v7m.net/security-validator",
                "webhook_endpoint": "https://asaas.v7m.net/webhook/",
                "events": [
                    "TRANSFER_CREATED",
                    "TRANSFER_DONE",
                    "TRANSFER_FAILED",
                    "PIX_TRANSACTION_CREATED",
                    "PIX_TRANSACTION_COMPLETED",
                    "PIX_TRANSACTION_CANCELLED",
                ],
                "account": {"name": "Empresa Ltda", "email": "api@empresa.com"},
                "instructions_html": "<ol>...</ol>",
            }
        }
    )


class ConfigConfirmResponse(BaseModel):
    ok: bool = Field(..., description="True se o webhook foi criado/recriado com sucesso")
    webhook_registered: dict[str, Any] = Field(
        ..., description="Objeto webhook retornado pelo Asaas"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "ok": True,
                "webhook_registered": {
                    "id": "8a3f2d1e-...",
                    "url": "https://asaas.v7m.net/webhook/",
                    "enabled": True,
                    "events": ["TRANSFER_DONE", "TRANSFER_FAILED"],
                },
            }
        }
    )


class ConfigStatusResponse(BaseModel):
    configured: dict[str, Any] = Field(
        ..., description="Configuracoes salvas, com secrets mascarados"
    )
    account: dict[str, Any] | None = Field(default=None, description="Conta Asaas conectada")
    balance: dict[str, Any] | None = Field(default=None, description="Saldo Asaas atual")
    webhook_registered: dict[str, Any] | None = Field(
        default=None, description="Webhook gerenciado encontrado no Asaas"
    )
    webhook_hmac_configured: bool = Field(
        default=False,
        description=("True se o webhook HMAC secret esta configurado (ou estamos em dev/staging)"),
    )
    errors: list[str] = Field(
        default_factory=list,
        description="Pendencias de configuracao ou falhas de consulta. Lista vazia = tudo ok.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "configured": {
                    "external_url": "https://asaas.v7m.net/",
                    "internal_url": "http://127.0.0.1:8081/",
                    "asaas_api_key": "$aact_prod_***",
                    "asaas_security_token": "a1b2***",
                },
                "account": {"name": "Empresa Ltda", "email": "api@empresa.com"},
                "balance": {"balance": 1234.56},
                "webhook_registered": {
                    "id": "8a3f2d1e-...",
                    "url": "https://asaas.v7m.net/webhook/",
                    "enabled": True,
                },
                "errors": [],
            }
        }
    )
