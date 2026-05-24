from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.schemas.checkout import CheckoutResponse
from app.schemas.error import ErrorResponse
from app.schemas.webhook import WebhookResponse
from app.services import checkout_service
from app.utils.crypto import decrypt_external_id

router = APIRouter()


@router.post(
    "/",
    response_model=WebhookResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Payload invalido"},
        404: {"model": ErrorResponse, "description": "Checkout desconhecido"},
        422: {"model": ErrorResponse, "description": "order_nsu diverge ou campos faltando"},
        502: {"model": ErrorResponse, "description": "Falha na validacao via InfinitePay"},
    },
)
async def infinitepay_webhook(
    request: Request,
    external_id: str = Query(...),
    db: AsyncSession = Depends(get_session),
):
    """Server-to-server webhook da InfinitePay — atualiza status do checkout.

    O external_id chega cifrado (Fernet) na query; token invalido => 422. A
    confirmacao do pagamento e feita out-of-band via payment_check antes de marcar pago.
    """
    external_id = decrypt_external_id(external_id)
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {"raw": payload}
    result = await checkout_service.handle_infinitepay_webhook(db, external_id, payload)
    await db.commit()
    return result


@router.get("/", response_model=CheckoutResponse)
async def checkout_status(
    order_nsu: str = Query(...),
    db: AsyncSession = Depends(get_session),
):
    """Consulta status de um checkout (nao altera nada)."""
    return await checkout_service.get_checkout(db, order_nsu)
