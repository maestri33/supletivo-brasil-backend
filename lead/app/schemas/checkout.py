"""Schemas do fluxo CHECKOUT."""

from app.schemas.base import APIModel
from app.schemas.captured import PixData


class CheckoutGetResponse(APIModel):
    status: str
    checkout_url: str | None = None
    pix: PixData | None = None
    message: str | None = None
