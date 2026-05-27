"""Schemas da etapa de chave PIX (validada e cadastrada no servico `asaas`).

A chave PIX e' usada para o candidato RECEBER comissoes quando virar promotor —
nao ha cobranca aqui. O asaas valida no DICT e confere o titular (CPF).
"""

from pydantic import Field

from app.schemas import APIModel


class PixKeyGetResponse(APIModel):
    message: str = "Cadastre sua chave PIX"
    key: str | None = None
    key_type: str | None = None
    holder_name: str | None = None
    bank_name: str | None = None


class PixKeyPostRequest(APIModel):
    key: str = Field(..., min_length=3, description="Chave PIX a validar no DICT")
    key_type: str = Field(..., description="CPF, CNPJ, EMAIL, PHONE ou EVP")


class PixKeyPostResponse(APIModel):
    status: str
    message: str = "Chave PIX validada, envie sua selfie"
    holder_name: str | None = None
    bank_name: str | None = None
