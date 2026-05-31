"""Schemas de consulta de checkout (via demilitarized)."""

from app.schemas.base import APIModel
from pydantic import Field


class CheckoutOut(APIModel):
    external_id: str
    name: str | None = None
    email: str | None = None
    status: str
    checkout_url: str | None = None
    boleto_url: str | None = None
    pix_payload: str | None = None
    pix_qr_url: str | None = None


class CheckoutPatch(APIModel):
    status: str = Field(..., description="Novo status do checkout")
    payment_proof: str | None = None
