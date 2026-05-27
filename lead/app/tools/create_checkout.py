"""Criacao de checkout no provider escolhido.

Duas entradas:

- `create_checkout_for_lead(external_id, payment_method)` — BG task para
  o branch CREDIT CARD (infinitepay). Mantida assincrona porque a UX nao
  exige resposta imediata: frontend recebe o link via polling em
  `/api/v1/demilitarized/checkouts/{external_id}`.

- `create_pix_checkout_for_lead(external_id, *, session)` — chamada
  SINCRONA do POST /captured quando `payment_method=pix`. Cria a cobranca,
  salva o QR PNG em `media/qrcodes/`, persiste o `lead.checkouts`,
  transiciona o Lead para CHECKOUT e devolve o Checkout pronto pra responder.
  Levanta `PixCheckoutError` em qualquer falha — caller traduz para HTTPException.

A mensageria (`_notify_*_checkout`) eh comum a ambos os branches.
"""

import asyncio
from datetime import date, timedelta
from pathlib import Path
from uuid import UUID

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import async_session_maker
from app.integrations.asaas import AsaasChargeCreate, AsaasClient, AsaasPayerIn
from app.integrations.infinitepay import CheckoutCreate, CustomerIn, InfinitePayClient
from app.integrations.notify import NotifyClient
from app.integrations.profiles import ProfilesClient
from app.models import Checkout, Lead, LeadStatus
from app.tools.messaging import notify_and_track
from app.tools.qrcode import absolute_qr_url, make_data_uri, save_pix_qr_png

logger = structlog.get_logger()
MESSAGES = Path(__file__).resolve().parent.parent / "notify" / "messages"

PAYMENT_METHODS = ("credit_card", "pix")


class PixCheckoutError(Exception):
    """Erro de dominio na criacao de PIX sincrono.

    `code` mapeia 1:1 com codigos curtos consumidos pelo frontend
    (ex.: `missing_cpf`, `asaas_unavailable`, `asaas_api_key_not_set`).
    """

    def __init__(self, code: str, detail: str = "", http_status: int = 502) -> None:
        self.code = code
        self.detail = detail
        self.http_status = http_status
        super().__init__(f"{code}: {detail}" if detail else code)


def _sanitize_phone(phone: str) -> str:
    """Remove DDI 55 e caracteres não numéricos para integração com InfinitePay."""
    cleaned = "".join(c for c in phone if c.isdigit())
    if cleaned.startswith("55") and len(cleaned) > 11:
        cleaned = cleaned[2:]
    return cleaned


async def _fetch_lead_context(external_id: str) -> tuple[str, str, str, str]:
    """Busca name, phone, email, cpf do lead nos servicos externos.

    cpf vem de profiles.get_one (necessario para criar customer no asaas).
    """
    async with (
        httpx.AsyncClient(
            base_url=settings.PROFILES_BASE_URL,
            timeout=settings.HTTP_TIMEOUT,
        ) as profiles_http,
        httpx.AsyncClient(
            base_url=settings.NOTIFY_BASE_URL,
            timeout=settings.HTTP_TIMEOUT,
        ) as notify_http,
    ):
        profiles = ProfilesClient(profiles_http)
        first = await profiles.first_name(external_id)
        try:
            full = await profiles.get_one(external_id)
        except Exception:
            full = {}
        contact = await NotifyClient(notify_http).get_contact(external_id)

    # Usa full_name (canonico do CPFHub); first_name e' so um truncamento.
    name = first.get("full_name") or first.get("first_name") or ""
    phone = contact.get("phone") or ""
    email = contact.get("email") or ""
    cpf = full.get("cpf") or ""
    return name, phone, email, cpf


# ── credit_card (BG task) ───────────────────────────────────────────────────


async def create_checkout_for_lead(external_id: str, payment_method: str = "credit_card") -> None:
    """Fluxo assincrono pos-WAITING — APENAS para credit_card.

    PIX usa o branch sincrono `create_pix_checkout_for_lead`; chamadas legadas
    a esta funcao com `payment_method='pix'` continuam funcionando para nao
    quebrar callers antigos, mas o flow sync ja persiste o Checkout antes do
    BG rodar (no-op idempotente).
    """
    if payment_method not in PAYMENT_METHODS:
        logger.error(
            "checkout_invalid_method",
            external_id=external_id,
            payment_method=payment_method,
        )
        return

    log = logger.bind(external_id=external_id, payment_method=payment_method)
    ext_uuid = UUID(external_id)

    name, phone, email, cpf = await _fetch_lead_context(external_id)
    if not name or not phone or not email:
        log.warning(
            "checkout_skip_missing_data",
            name=bool(name),
            phone=bool(phone),
            email=bool(email),
        )
        return

    encoded_image_b64: str | None = None
    if payment_method == "pix":
        # Caminho legado / fallback. Cria sync e devolve None se falhar.
        try:
            checkout_row, encoded_image_b64 = await _create_pix_checkout(
                ext_uuid,
                external_id,
                name,
                phone,
                email,
                cpf,
            )
        except PixCheckoutError as exc:
            log.error("pix_bg_failed", code=exc.code, detail=exc.detail)
            return
    else:
        checkout_row = await _create_credit_card_checkout(
            log,
            ext_uuid,
            external_id,
            name,
            phone,
            email,
        )

    if checkout_row is None:
        return

    # Promove lead para CHECKOUT (idempotente — se ja estiver em CHECKOUT pelo
    # branch sync, no-op).
    promoter_external_id: UUID | None = None
    async with async_session_maker() as session:
        existing = await session.scalar(select(Checkout).where(Checkout.external_id == ext_uuid))
        if existing is None:
            session.add(checkout_row)
        lead = await session.scalar(select(Lead).where(Lead.external_id == ext_uuid))
        if not lead:
            log.error("lead_not_found")
            return
        if lead.status != LeadStatus.CHECKOUT:
            lead.status = LeadStatus.CHECKOUT
        promoter_external_id = lead.promoter_external_id
        await session.commit()

    log.info("checkout_created", provider=checkout_row.provider)

    customer_link = checkout_row.checkout_url or checkout_row.qrcode_payload or ""
    qr_abs = absolute_qr_url(checkout_row.qrcode_image) if checkout_row.qrcode_image else ""
    await asyncio.gather(
        _notify_lead_checkout(
            external_id,
            customer_link,
            qr_abs,
            payment_method,
            encoded_image_b64,
        ),
        _notify_promoter_checkout(
            external_id,
            phone,
            name,
            customer_link,
            qr_abs,
            promoter_external_id,
            payment_method,
            encoded_image_b64,
        ),
    )


async def _create_credit_card_checkout(
    log,
    ext_uuid: UUID,
    external_id: str,
    name: str,
    phone: str,
    email: str,
) -> Checkout | None:
    """Cria checkout via InfinitePay (cartao de credito)."""
    async with httpx.AsyncClient(
        base_url=settings.INFINITEPAY_BASE_URL,
        timeout=settings.HTTP_TIMEOUT,
    ) as ip_http:
        ip_client = InfinitePayClient(ip_http)
        try:
            checkout_out = await ip_client.create_checkout(
                CheckoutCreate(
                    external_id=external_id,
                    customer=CustomerIn(
                        name=name,
                        email=email,
                        phone_number=_sanitize_phone(phone),
                    ),
                )
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 409:
                log.info("checkout_already_exists")
                checkout_out = await ip_client.get_checkout(external_id)
            else:
                log.error(
                    "checkout_create_failed",
                    status=exc.response.status_code,
                    body=exc.response.text[:500],
                )
                return None
        except Exception as exc:
            log.error("checkout_create_failed", error=str(exc))
            return None

    return Checkout(
        external_id=ext_uuid,
        payment_method="credit_card",
        provider="infinitepay",
        provider_payment_id=external_id,  # infinitepay usa external_id direto como id
        checkout_url=checkout_out.checkout_url,
        receipt_url=checkout_out.receipt_url,
        invoice_slug=checkout_out.invoice_slug,
        transaction_nsu=checkout_out.transaction_nsu,
        capture_method=checkout_out.capture_method,
        installments=checkout_out.installments,
        is_paid=checkout_out.is_paid,
    )


# ── pix (sync) ──────────────────────────────────────────────────────────────


async def _create_pix_checkout(
    ext_uuid: UUID,
    external_id: str,
    name: str,
    phone: str,
    email: str,
    cpf: str,
) -> tuple[Checkout, str | None]:
    """Cria cobranca PIX via asaas, salva QR PNG em media/qrcodes/.

    Levanta PixCheckoutError em qualquer falha. NAO persiste Checkout —
    caller faz `session.add(checkout)` + commit.

    Returns:
        (checkout, encoded_image_b64) — base64 raw do QR (sem prefixo data:)
        retornado pelo asaas; usado downstream pra anexar a imagem como
        midia na mensagem WhatsApp via data URI.
    """
    log = logger.bind(external_id=external_id, payment_method="pix")
    if not cpf:
        log.warning("pix_skip_missing_cpf")
        raise PixCheckoutError("missing_cpf", "Profile sem CPF (CPFHub falhou?)", http_status=422)

    due_date_str: str | None = None
    if settings.PIX_DEFAULT_DUE_DAYS is not None:
        due = date.today() + timedelta(days=settings.PIX_DEFAULT_DUE_DAYS)
        due_date_str = due.isoformat()

    payload = AsaasChargeCreate(
        external_id=external_id,
        amount=settings.PIX_DEFAULT_AMOUNT,
        description=settings.PIX_DEFAULT_DESCRIPTION,
        due_date=due_date_str,
        payer=AsaasPayerIn(
            name=name,
            cpf_cnpj=cpf,
            email=email,
            # Asaas rejeita o DDI 55 prefixado — espera apenas DDD+numero
            # (10 ou 11 digitos). Mesmo sanitize aplicado ao InfinitePay.
            mobile_phone=_sanitize_phone(phone),
        ),
    )

    async with httpx.AsyncClient(
        base_url=settings.ASAAS_BASE_URL,
        timeout=settings.HTTP_TIMEOUT,
    ) as asaas_http:
        try:
            charge = await AsaasClient(asaas_http).create_charge_pix(payload)
        except httpx.HTTPStatusError as exc:
            detail: str
            try:
                body = exc.response.json()
                if isinstance(body, dict):
                    detail = body.get("detail", exc.response.text[:200])
                else:
                    detail = str(body)[:200]
            except Exception:
                detail = exc.response.text[:200]
            log.error(
                "pix_create_failed",
                status=exc.response.status_code,
                detail=str(detail)[:200],
            )
            # Codigos conhecidos do asaas (ver INTEGRATION.md) — bubble up.
            code = "asaas_error"
            if isinstance(detail, str):
                first_token = detail.split(":")[0].strip() if ":" in detail else detail.strip()
                if first_token in {
                    "asaas_api_key_not_set",
                    "asaas_customer_create_failed",
                    "asaas_charge_create_failed",
                    "invalid_amount",
                    "invalid_due_date",
                    "invalid_cpf_cnpj",
                    "customer_required",
                }:
                    code = first_token
            raise PixCheckoutError(code, str(detail), http_status=502) from exc
        except Exception as exc:
            log.error("pix_create_failed", error=str(exc))
            raise PixCheckoutError("asaas_unavailable", str(exc), http_status=502) from exc

    pix = charge.pix
    qr_url_relative: str | None = None
    encoded_image_b64: str | None = None
    if pix and pix.encoded_image:
        encoded_image_b64 = pix.encoded_image
        try:
            qr_url_relative = save_pix_qr_png(external_id, pix.encoded_image)
        except Exception as exc:
            # Frontend pode buscar via GET /api/v1/charge/{payment_id} no asaas
            # ou rebuscar via POST /qr — nao bloqueia a transicao do lead.
            log.warning("qr_save_failed", error=str(exc))

    checkout = Checkout(
        external_id=ext_uuid,
        payment_method="pix",
        provider="asaas",
        provider_payment_id=charge.payment_id,
        capture_method="pix",
        installments=1,
        qrcode_payload=pix.payload if pix else None,
        qrcode_image=qr_url_relative,  # URL relativa ('/api/v1/public/media/qrcodes/<eid>.png')
        due_date=charge.due_date,
        is_paid=charge.status == "PAID",
    )
    return checkout, encoded_image_b64


async def create_pix_checkout_for_lead(
    external_id: str,
    *,
    session: AsyncSession,
) -> Checkout:
    """Fluxo SINCRONO completo do PIX. Usado pelo POST /captured.

    1. Busca context (profiles + notify)
    2. Cria cobranca asaas + salva QR PNG
    3. Persiste Checkout + transiciona Lead para CHECKOUT (na MESMA session)
    4. Dispara mensagens em BG (fire-and-forget)
    5. Devolve o Checkout pronto

    Levanta `PixCheckoutError` em qualquer falha. Caller (route handler)
    traduz para HTTPException com o `http_status` apropriado.
    """
    log = logger.bind(external_id=external_id, payment_method="pix")
    ext_uuid = UUID(external_id)

    name, phone, email, cpf = await _fetch_lead_context(external_id)
    if not name or not phone or not email:
        raise PixCheckoutError(
            "incomplete_context",
            f"name={bool(name)} phone={bool(phone)} email={bool(email)}",
            http_status=422,
        )

    checkout, encoded_image_b64 = await _create_pix_checkout(
        ext_uuid,
        external_id,
        name,
        phone,
        email,
        cpf,
    )

    # Persiste + transiciona na mesma session.
    session.add(checkout)
    lead = await session.scalar(select(Lead).where(Lead.external_id == ext_uuid))
    if not lead:
        # session sera rolled back pelo caller (HTTPException)
        raise PixCheckoutError("lead_not_found", "", http_status=404)
    promoter_external_id = lead.promoter_external_id
    if lead.status != LeadStatus.CHECKOUT:
        lead.status = LeadStatus.CHECKOUT
    await session.commit()
    await session.refresh(checkout)

    log.info("checkout_created", provider="asaas", payment_id=checkout.provider_payment_id)

    # Mensageria em background (nao bloqueia a resposta).
    # Para PIX, manda 2 mensagens: texto explicativo + imagem do QR anexada
    # (com BR Code no caption) — ver _notify_lead_checkout.
    customer_link = checkout.qrcode_payload or ""
    qr_abs = absolute_qr_url(checkout.qrcode_image) if checkout.qrcode_image else ""
    asyncio.create_task(
        _notify_checkout_safely(
            external_id,
            phone,
            name,
            customer_link,
            qr_abs,
            promoter_external_id,
            "pix",
            encoded_image_b64,
        )
    )

    return checkout


async def _notify_checkout_safely(
    external_id: str,
    phone: str,
    first_name: str,
    customer_link: str,
    qr_abs: str,
    promoter_id: UUID | None,
    payment_method: str,
    encoded_image_b64: str | None = None,
) -> None:
    """Wrapper safe — qualquer excecao e' so logada, nunca cancela o flow."""
    try:
        await asyncio.gather(
            _notify_lead_checkout(
                external_id,
                customer_link,
                qr_abs,
                payment_method,
                encoded_image_b64,
            ),
            _notify_promoter_checkout(
                external_id,
                phone,
                first_name,
                customer_link,
                qr_abs,
                promoter_id,
                payment_method,
                encoded_image_b64,
            ),
        )
    except Exception as exc:
        logger.error("notify_checkout_failed", external_id=external_id, error=str(exc))


# ── Mensageria ──────────────────────────────────────────────────────────────


async def _notify_lead_checkout(
    external_id: str,
    customer_link: str,
    qr_url: str,
    payment_method: str,
    encoded_image_b64: str | None = None,
) -> None:
    """Envia mensagem(s) de checkout pro lead.

    PIX (com encoded_image_b64): manda DUAS mensagens —
      1. Texto explicativo (template `checkout_lead_pix.md`).
      2. QR PNG anexado via data URI (`media_url=data:image/png;base64,...`)
         com o BR Code no caption. WhatsApp recebe imagem real + codigo
         copia-e-cola juntos.

    Credit card / PIX sem b64 (fallback): manda 1 mensagem texto.
    """
    template_name = "checkout_lead_pix.md" if payment_method == "pix" else "checkout_lead.md"
    template_path = MESSAGES / template_name
    if not template_path.exists():
        template_path = MESSAGES / "checkout_lead.md"
    template = template_path.read_text(encoding="utf-8")
    content = (
        template.replace("{{checkout_url}}", customer_link)
        .replace("{{pix_payload}}", customer_link)
        .replace("{{qr_url}}", qr_url)
    )
    # Mensagem 1: texto explicativo.
    await notify_and_track(external_id, content, event="checkout_lead")

    # Mensagem 2 (so PIX): imagem do QR anexada via data URI base64.
    # Notify extrai o base64 puro e passa direto pra Evolution API, que
    # envia como midia binaria inline no WhatsApp (caption=BR Code).
    if payment_method == "pix" and encoded_image_b64:
        caption_template_path = MESSAGES / "checkout_lead_pix_qr.md"
        if caption_template_path.exists():
            caption = caption_template_path.read_text(encoding="utf-8").replace(
                "{{pix_payload}}",
                customer_link,
            )
        else:
            # Fallback: caption minimo com so o BR Code (copia-e-cola direto).
            caption = customer_link
        await notify_and_track(
            external_id,
            caption,
            media_url=make_data_uri(encoded_image_b64),
            title="QR Code PIX",
            event="checkout_lead_qr",
        )


async def _notify_promoter_checkout(
    external_id: str,
    phone: str,
    first_name: str,
    customer_link: str,
    qr_url: str,
    promoter_id: UUID | None,
    payment_method: str,
    encoded_image_b64: str | None = None,
) -> None:
    if not promoter_id:
        return
    template_name = (
        "checkout_promoter_pix.md" if payment_method == "pix" else "checkout_promoter.md"
    )
    template_path = MESSAGES / template_name
    if not template_path.exists():
        template_path = MESSAGES / "checkout_promoter.md"
    template = template_path.read_text(encoding="utf-8")
    content = (
        template.replace("{{first_name}}", first_name)
        .replace("{{phone}}", phone)
        .replace("{{checkout_url}}", customer_link)
        .replace("{{pix_payload}}", customer_link)
        .replace("{{qr_url}}", qr_url)
    )
    await notify_and_track(str(promoter_id), content, event="checkout_promoter")

    # Promoter tambem recebe o QR anexado pra poder repassar/conferir.
    if payment_method == "pix" and encoded_image_b64:
        caption = f"QR Code PIX de {first_name} ({phone}):\n\n{customer_link}"
        await notify_and_track(
            str(promoter_id),
            caption,
            media_url=make_data_uri(encoded_image_b64),
            title=f"QR PIX — {first_name}",
            event="checkout_promoter_qr",
        )
