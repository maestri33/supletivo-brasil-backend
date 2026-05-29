from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.schemas.checkout import CheckoutResponse
from app.schemas.error import ErrorResponse
from app.schemas.webhook import WebhookResponse
from app.services import checkout_service
from app.services.webhook_security import verify_hmac, verify_ip_allowlist
from app.utils.crypto import decrypt_external_id
from app.utils.net import client_ip, user_agent

router = APIRouter()


@router.post(
    "/",
    response_model=WebhookResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Payload invalido"},
        401: {"model": ErrorResponse, "description": "Assinatura HMAC invalida"},
        403: {"model": ErrorResponse, "description": "IP nao autorizado"},
        404: {"model": ErrorResponse, "description": "Checkout desconhecido"},
        422: {"model": ErrorResponse, "description": "order_nsu diverge ou campos faltando"},
        502: {"model": ErrorResponse, "description": "Falha na validacao via InfinitePay"},
    },
)
async def infinitepay_webhook(
    request: Request,
    external_id: str = Query(...),
    db: AsyncSession = Depends(get_session),
    _ip: None = Depends(verify_ip_allowlist),
    _sig: None = Depends(verify_hmac),
):
    """Server-to-server webhook da InfinitePay — atualiza status do checkout.

    O external_id chega cifrado (Fernet) na query; token invalido => 422. A
    confirmacao do pagamento e feita out-of-band via payment_check antes de marcar pago.

    Seguranca (defesa em profundidade):
    1. IP allow-list — INFINITEPAY_WEBHOOK_ALLOWED_CIDRS (camada 1)
    2. HMAC signature — x-infinitepay-signature com INFINITEPAY_WEBHOOK_SECRET (camada 2)
    Ambas sao opcionais em dev (sem secret = bypass), obrigatorias em producao.
    """
    external_id = decrypt_external_id(external_id)
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {"raw": payload}
    result = await checkout_service.handle_infinitepay_webhook(
        db,
        external_id,
        payload,
        source_ip=client_ip(request),
        user_agent=user_agent(request),
    )
    await db.commit()
    return result


@router.get("/", response_model=CheckoutResponse)
async def checkout_status(
    order_nsu: str = Query(...),
    db: AsyncSession = Depends(get_session),
):
    """Consulta status de um checkout (nao altera nada)."""
    return await checkout_service.get_checkout(db, order_nsu)
