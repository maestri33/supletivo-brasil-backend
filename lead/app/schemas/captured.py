"""Schemas do fluxo CAPTURED — coleta de dados do lead."""

from typing import Literal

from app.schemas.base import APIModel
from pydantic import EmailStr, Field


PaymentMethod = Literal["credit_card", "pix"]


class CapturedGetResponse(APIModel):
    message: str = "Insira seus dados para prosseguir"
    name: str | None = None
    phone: str | None = None
    email: str | None = None


class CapturedPostRequest(APIModel):
    """Phone e nome (quando ja vindo do CPFHub via profiles) sao imutaveis."""

    name: str | None = Field(default=None, min_length=2, max_length=120)
    email: EmailStr
    payment_method: PaymentMethod = Field(default="credit_card")


class PixData(APIModel):
    """Dados PIX retornados no flow sincrono. Null para credit_card."""

    payment_id: str
    payload: str
    qr_url: str


class CapturedPostResponse(APIModel):
    status: str
    message: str = "Dados salvos, aguarde processamento"
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    payment_method: str | None = None
    pix: PixData | None = None
