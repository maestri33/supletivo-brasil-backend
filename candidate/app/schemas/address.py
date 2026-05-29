"""Schemas da etapa de endereco (persistido no servico `address`)."""

from pydantic import Field

from app.schemas import APIModel


class AddressGetResponse(APIModel):
    message: str = "Preencha seu endereco"
    cep: str | None = None
    street: str | None = None
    number: str | None = None
    complement: str | None = None
    neighborhood: str | None = None
    city: str | None = None
    state: str | None = None
    has_proof: bool = False
    proof_file: str | None = None


class CepCheckResponse(APIModel):
    cep: str
    formatted: str
    valid: bool
    street: str | None = None
    neighborhood: str | None = None
    city: str | None = None
    state: str | None = None


class AddressPostRequest(APIModel):
    cep: str = Field(..., min_length=8, max_length=9, description="CEP com ou sem mascara")
    street: str = Field(..., min_length=2, max_length=255)
    number: str = Field(..., min_length=1, max_length=20)
    complement: str | None = Field(None, max_length=255)
    neighborhood: str = Field(..., min_length=2, max_length=100)
    city: str = Field(..., min_length=2, max_length=100)
    state: str = Field(..., min_length=2, max_length=2)


class AddressPostResponse(APIModel):
    status: str
    message: str = "Endereco salvo, envie seus documentos"
