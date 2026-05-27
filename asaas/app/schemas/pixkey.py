"""Schemas de chave Pix (PixKey)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PixKeyResponse(BaseModel):
    """Chave Pix cadastrada e validada no DICT."""

    external_id: str = Field(..., description="ID do destinatario no sistema cliente")
    key: str = Field(..., description="Chave Pix")
    key_type: str = Field(..., description="CPF | CNPJ | EMAIL | PHONE | EVP")
    holder_document: str = Field(
        ..., description="CPF (11 digitos) ou CNPJ (14 digitos) do titular"
    )
    holder_name: str | None = Field(default=None, description="Nome do titular retornado pelo DICT")
    bank_name: str | None = Field(default=None, description="Nome do banco do titular")
    validated_at: str | None = Field(
        default=None, description="Timestamp ISO 8601 da validacao DICT"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "external_id": "diandra_celular",
                "key": "+554****1770",
                "key_type": "PHONE",
                "holder_document": "07461638947",
                "holder_name": "Diandra S.",
                "bank_name": "SICOOB",
                "validated_at": "2026-04-24T17:30:00",
            }
        }
    )


class PixKeyCheckResponse(BaseModel):
    """Resultado de consulta de chave Pix (com ou sem persistencia)."""

    source: str = Field(
        ..., description='"db" se ja cadastrada localmente, "dict" se consultada ao vivo no DICT'
    )
    data: dict[str, Any] = Field(
        ..., description="Dados do titular. Campos identicos a PixKeyResponse quando source=db."
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "source": "dict",
                "data": {
                    "key": "+554****1770",
                    "holder_document": "074.***.**9-47",
                    "holder_name": "Diandra S.",
                    "bank_name": "SICOOB",
                },
            }
        }
    )
