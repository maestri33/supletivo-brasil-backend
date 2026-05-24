from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.schemas.checkout import CheckoutCreate, CheckoutListResponse, CheckoutResponse
from app.schemas.error import ErrorResponse
from app.services import checkout_service

router = APIRouter()


@router.post(
    "/",
    response_model=CheckoutResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Campos obrigatorios ausentes"},
        409: {"model": ErrorResponse, "description": "external_id ja existe"},
        422: {"model": ErrorResponse, "description": "Validacao de campos"},
        502: {"model": ErrorResponse, "description": "Falha na InfinitePay"},
    },
)
async def create(
    body: CheckoutCreate, db: AsyncSession = Depends(get_session)
) -> CheckoutResponse:
    """Cria um link de pagamento InfinitePay.

    handle, price, description, redirect_url e public_api_url usam os defaults
    do .env quando nao informados no body.
    """
    result = await checkout_service.create_checkout(db, body.model_dump(exclude_unset=True))
    await db.commit()
    return result


@router.get("/", response_model=CheckoutListResponse)
async def list_all(db: AsyncSession = Depends(get_session)) -> CheckoutListResponse:
    """Lista todos os checkouts, do mais recente ao mais antigo."""
    return {"items": await checkout_service.list_checkouts(db)}


@router.get(
    "/{external_id}/",
    response_model=CheckoutResponse,
    responses={404: {"model": ErrorResponse, "description": "Checkout nao encontrado"}},
)
async def get_one(
    external_id: str, db: AsyncSession = Depends(get_session)
) -> CheckoutResponse:
    """Consulta um checkout pelo external_id.

    Se pago, retorna receipt_url. Senao, retorna checkout_url para pagamento.
    """
    return await checkout_service.get_checkout(db, external_id)
