"""Endpoint authenticated/captured — primeiro passo após login."""

from typing import Literal
from uuid import UUID

import httpx
import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.dependencies import require_captured
from app.integrations.notify import NotifyClient
from app.integrations.profiles import ProfilesClient
from app.models import Lead, LeadStatus
from app.schemas import APIModel
from app.tools.create_checkout import (
    PixCheckoutError,
    create_checkout_for_lead,
    create_pix_checkout_for_lead,
)
from app.tools.qrcode import absolute_qr_url

router = APIRouter(prefix="/api/v1/authenticated", tags=["authenticated"])

logger = structlog.get_logger()

PaymentMethod = Literal["credit_card", "pix"]


class CapturedGetResponse(APIModel):
    message: str = "Insira seus dados para prosseguir"
    name: str | None = None
    phone: str | None = None
    email: str | None = None


class CapturedPostRequest(APIModel):
    """Phone e nome (quando ja vindo do CPFHub via profiles) sao imutaveis.

    Fontes de verdade:
      - phone: notify (set no register, imutavel daqui em diante)
      - name:  profiles (auto-populado por CPFHub no register; imutavel se ja setado)
      - email: notify (settable aqui)

    Regras de name:
      - `name` e opcional. Se vier no payload:
          * E profile ja tem name diferente => 422 name_immutable
          * E profile nao tem name => patch profiles com o novo
          * E profile ja tem name igual => no-op (idempotente)
      - Se `name` nao vier no payload e profile nao tem name => 422 name_required

    payment_method:
      - 'credit_card' (default) => infinitepay (BG; frontend polla
        `/api/v1/demilitarized/checkouts/{external_id}` para obter checkout_url)
      - 'pix'                   => asaas (SINCRONO; resposta ja traz pix_payload
        + pix_qr_url + payment_id, e lead pula direto para CHECKOUT)
    """

    name: str | None = Field(default=None, min_length=2, max_length=120)
    email: EmailStr
    payment_method: PaymentMethod = Field(default="credit_card")


class PixData(APIModel):
    """Dados PIX retornados no flow sincrono. Null para credit_card."""

    payment_id: str
    payload: str  # BR Code copia-e-cola
    qr_url: str  # URL absoluta do PNG (renderiza com <img src>)


class CapturedPostResponse(APIModel):
    status: str
    message: str = "Dados salvos, aguarde processamento"
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    payment_method: PaymentMethod | None = None
    pix: PixData | None = None


def is_blank(value: str | None) -> bool:
    return not value or value.strip() == ""


async def fetch_lead_context(external_id: str):
    async with (
        httpx.AsyncClient(
            base_url=settings.PROFILES_BASE_URL, timeout=settings.HTTP_TIMEOUT,
        ) as profiles_http,
        httpx.AsyncClient(
            base_url=settings.NOTIFY_BASE_URL, timeout=settings.HTTP_TIMEOUT,
        ) as notify_http,
    ):
        profile_data = await ProfilesClient(profiles_http).first_name(external_id)
        contact_data = await NotifyClient(notify_http).get_contact(external_id)
    return profile_data, contact_data


@router.get("/captured", response_model=CapturedGetResponse, summary="Busca dados do lead capturado")
async def get_captured(external_id: UUID = require_captured()):
    profile_data, contact_data = await fetch_lead_context(str(external_id))
    # Retorna full_name (canonico, vindo do CPFHub) — primeiro nome derivavel
    # no frontend via split(" ")[0]. Coerente com a regra de imutabilidade
    # do POST (que compara contra full_name).
    return CapturedGetResponse(
        name=profile_data.get("full_name") or profile_data.get("first_name"),
        phone=contact_data.get("phone"),
        email=contact_data.get("email"),
    )


@router.post(
    "/captured",
    response_model=CapturedPostResponse,
    summary="Completa cadastro e avança lead",
)
async def post_captured(
    payload: CapturedPostRequest,
    background_tasks: BackgroundTasks,
    external_id: UUID = require_captured(),
    session: AsyncSession = Depends(get_session),
):
    external_id_str = str(external_id)
    log = logger.bind(external_id=external_id_str, payment_method=payload.payment_method)
    errors: dict[str, str] = {}

    # 1) Buscar estado canonico antes de qualquer mutacao
    profile_data, contact_data = await fetch_lead_context(external_id_str)
    # Comparamos sempre contra full_name (canonico do CPFHub) — first_name
    # e um truncamento derivado e nunca deve ser usado como fonte de verdade.
    existing_name = profile_data.get("full_name") or profile_data.get("first_name") or ""

    # 2) Regra do nome: imutavel quando ja existe (vindo do CPFHub)
    submitted_name = (payload.name or "").strip() or None
    if existing_name:
        if submitted_name and submitted_name != existing_name:
            log.warning(
                "name_immutable_rejected",
                existing_first=existing_name.split()[0] if existing_name else None,
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "name": "name_immutable: ja definido (CPFHub). Nao pode ser alterado.",
                },
            )
        # else: payload sem name OU mesmo name => nada a fazer no profile.
    else:
        # Profile nao tem name (CPFHub falhou / CPF nao encontrado).
        if not submitted_name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"name": "name_required"},
            )
        async with httpx.AsyncClient(
            base_url=settings.PROFILES_BASE_URL, timeout=settings.HTTP_TIMEOUT,
        ) as client:
            try:
                await ProfilesClient(client).patch(external_id_str, name=submitted_name)
            except httpx.HTTPStatusError as exc:
                try:
                    detail = exc.response.json()
                except Exception:
                    detail = exc.response.text
                errors["name"] = str(detail)

    # 3) Email: sempre settable
    async with httpx.AsyncClient(
        base_url=settings.NOTIFY_BASE_URL, timeout=settings.HTTP_TIMEOUT,
    ) as client:
        try:
            await NotifyClient(client).update_email(external_id_str, payload.email)
        except httpx.HTTPStatusError as exc:
            try:
                detail = exc.response.json()
            except Exception:
                detail = exc.response.text
            errors["email"] = str(detail)

    if errors:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=errors)

    # 4) Recarregar estado canonico depois das mutacoes
    profile_data, contact_data = await fetch_lead_context(external_id_str)
    current_name = profile_data.get("full_name") or profile_data.get("first_name") or ""
    current_phone = contact_data.get("phone") or ""
    current_email = contact_data.get("email") or ""

    if is_blank(current_name) or is_blank(current_email) or is_blank(current_phone):
        return CapturedPostResponse(
            status="incomplete",
            message="Preencha todos os campos para prosseguir",
            name=current_name or None,
            phone=current_phone or None,
            email=current_email or None,
            payment_method=payload.payment_method,
        )

    # 5) Carrega o Lead e ramifica por payment_method
    lead = await session.scalar(select(Lead).where(Lead.external_id == external_id))
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead nao encontrado")

    # 5a) PIX — SINCRONO. Cria cobranca, salva QR PNG, transiciona CHECKOUT,
    # devolve `pix_payload + pix_qr_url + payment_id` na resposta.
    if payload.payment_method == "pix":
        try:
            checkout = await create_pix_checkout_for_lead(external_id_str, session=session)
        except PixCheckoutError as exc:
            log.error("pix_sync_failed", code=exc.code, detail=exc.detail)
            raise HTTPException(
                status_code=exc.http_status,
                detail={"pix": f"{exc.code}: {exc.detail}" if exc.detail else exc.code},
            ) from exc

        pix_data = PixData(
            payment_id=checkout.provider_payment_id or "",
            payload=checkout.qrcode_payload or "",
            qr_url=absolute_qr_url(checkout.qrcode_image) if checkout.qrcode_image else "",
        )
        # session ja foi commitada dentro de create_pix_checkout_for_lead
        return CapturedPostResponse(
            status=LeadStatus.CHECKOUT.value,
            message="Cobranca PIX gerada. Pague para finalizar.",
            name=current_name,
            phone=current_phone,
            email=current_email,
            payment_method="pix",
            pix=pix_data,
        )

    # 5b) credit_card — assincrono. Lead → WAITING + BG cria checkout infinitepay.
    if lead.status == LeadStatus.CAPTURED:
        lead.status = LeadStatus.WAITING
        await session.commit()
        background_tasks.add_task(
            create_checkout_for_lead, external_id_str, payload.payment_method,
        )

    return CapturedPostResponse(
        status=lead.status.value,
        name=current_name,
        phone=current_phone,
        email=current_email,
        payment_method=payload.payment_method,
    )
