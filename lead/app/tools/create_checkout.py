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
from app.tools.qrcode import make_data_uri

logger = structlog.get_logger()
MESSAGES = Path(__file__).resolve().parent.parent / "notify" / "messages"

PAYMENT_METHODS = ("credit_card", "pix")


async def _mark_lead_failed(ext_uuid: UUID, reason: str) -> None:
    """Transiciona o Lead para FAILED quando o BG task de checkout esgota retries.

    Abre uma session propria (BG task nao tem a session do request) e e' idempotente:
    so transita se ainda estiver em WAITING. Falha silenciosa no log — o BG task ja
    falhou; nao queremos mascarar isso com erro de DB.
    """
    try:
        async with async_session_maker() as session:
            lead = await session.scalar(select(Lead).where(Lead.external_id == ext_uuid))
            if lead and lead.status == LeadStatus.WAITING:
                lead.status = LeadStatus.FAILED
                lead.failed_reason = reason[:80]
                await session.commit()
    except Exception as exc:
        logger.error("mark_lead_failed_error", external_id=str(ext_uuid), error=str(exc))


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

    # _fetch_lead_context bate em profiles + notify por HTTP. Se um deles
    # estiver fora, a excecao subiria e mataria o BG task em silencio —
    # deixando o lead ETERNO em WAITING (front nunca recebe erro). Capturamos
    # e transicionamos pra FAILED pra que /waiting devolva error_code.
    try:
        name, phone, email, cpf = await _fetch_lead_context(external_id)
    except Exception as exc:
        log.error("checkout_context_fetch_failed", error=str(exc))
        await _mark_lead_failed(ext_uuid, "context_fetch_failed")
        return

    if not name or not phone or not email:
        log.warning(
            "checkout_skip_missing_data",
            name=bool(name),
            phone=bool(phone),
            email=bool(email),
        )
        # Mesmo racional do fetch acima: sem marcar FAILED o lead fica preso
        # em WAITING e o /waiting nunca devolve error_code pro front.
        await _mark_lead_failed(ext_uuid, "context_incomplete")
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
    # qrcode_image ja vem ABSOLUTA pos-refactor (servida pelo asaas).
    qr_abs = checkout_row.qrcode_image or ""
    payment_id = checkout_row.provider_payment_id or ""
    due_date_iso = checkout_row.due_date.isoformat() if checkout_row.due_date else None
    await asyncio.gather(
        _notify_lead_checkout(
            external_id,
            customer_link,
            qr_abs,
            payment_id,
            email,
            phone,
            name,
            payment_method,
            encoded_image_b64,
            due_date_iso,
        ),
        _notify_promoter_checkout(
            external_id,
            phone,
            name,
            customer_link,
            qr_abs,
            payment_id,
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
                await _mark_lead_failed(ext_uuid, "checkout_create_failed")
                return None
        except Exception as exc:
            log.error("checkout_create_failed", error=str(exc))
            await _mark_lead_failed(ext_uuid, "checkout_create_failed")
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
    encoded_image_b64: str | None = None
    qr_url: str | None = None
    if pix:
        encoded_image_b64 = pix.encoded_image or None
        # qr_url ja vem ABSOLUTA do asaas (servido em
        # /api/v1/public/media/qrcodes/<payment_id>.png).
        # Lead nao salva mais o PNG localmente — asaas e' dono do binario.
        qr_url = pix.qr_url or None

    checkout = Checkout(
        external_id=ext_uuid,
        payment_method="pix",
        provider="asaas",
        provider_payment_id=charge.payment_id,
        capture_method="pix",
        installments=1,
        qrcode_payload=pix.payload if pix else None,
        # qrcode_image guarda URL ABSOLUTA servida pelo asaas (pos-refactor).
        # Registros antigos podem ter URL relativa `/api/v1/public/media/...`
        # do lead — alembic migration 2026-05-28_qrcode_url_to_asaas reescreve.
        qrcode_image=qr_url,
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
    # Para PIX, manda 3 etapas: texto explicativo + WhatsApp QR imagem +
    # email dedicado "Seu PIX Supletivo Brasil" — ver _notify_lead_checkout.
    customer_link = checkout.qrcode_payload or ""
    qr_abs = checkout.qrcode_image or ""
    payment_id = checkout.provider_payment_id or ""
    due_date_iso = checkout.due_date.isoformat() if checkout.due_date else None
    task = asyncio.create_task(
        _notify_checkout_safely(
            external_id,
            phone,
            name,
            email,
            customer_link,
            qr_abs,
            payment_id,
            promoter_external_id,
            "pix",
            encoded_image_b64,
            due_date_iso,
        )
    )
    # Sem ref forte, asyncio pode GC o BG task antes dele completar —
    # entrega silenciosa do email/imagem some. Set modulo-level segura
    # a vida do task ate done_callback remover.
    _BG_NOTIFY_TASKS.add(task)
    task.add_done_callback(_BG_NOTIFY_TASKS.discard)

    return checkout


_BG_NOTIFY_TASKS: set[asyncio.Task] = set()


async def _notify_checkout_safely(
    external_id: str,
    phone: str,
    first_name: str,
    email: str,
    customer_link: str,
    qr_abs: str,
    payment_id: str,
    promoter_id: UUID | None,
    payment_method: str,
    encoded_image_b64: str | None = None,
    due_date_iso: str | None = None,
) -> None:
    """Wrapper safe — qualquer excecao e' so logada, nunca cancela o flow.

    `due_date_iso` (YYYY-MM-DD) e usado pelo email rico do PIX como linha
    de vencimento condicional (so renderiza se nao-None).
    """
    try:
        await asyncio.gather(
            _notify_lead_checkout(
                external_id,
                customer_link,
                qr_abs,
                payment_id,
                email,
                phone,
                first_name,
                payment_method,
                encoded_image_b64,
                due_date_iso,
            ),
            _notify_promoter_checkout(
                external_id,
                phone,
                first_name,
                customer_link,
                qr_abs,
                payment_id,
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
    payment_id: str,
    email: str,
    phone: str,
    first_name: str,
    payment_method: str,
    encoded_image_b64: str | None = None,
    due_date_iso: str | None = None,
) -> None:
    """Envia mensagem(s) de checkout pro lead.

    PIX (com encoded_image_b64): 3 etapas explicitas, cada uma com
    `pix_notify_step` logging (step, status, message_id, error):

      1. WhatsApp + Email texto teaser "Cobranca PIX gerada!" (compat —
         `channels=None`). Template `checkout_lead_pix.md`.
      2. WhatsApp QR PNG (data URI) + caption copia-e-cola.
         `channels=['whatsapp']` — NAO duplica no email.
      3. Email dedicado "Seu PIX Supletivo Brasil" com QR embedado (CID),
         copia-e-cola, instrucoes e vencimento (se existir).
         `channels=['email']` — NAO duplica no WhatsApp.

    Cada etapa roda em seu proprio try/except: falha em (2) nao impede
    (3) de tentar. Erro especifico vai pra log com event
    `pix_notify_step_failed` (sem retry — notify ja tem retry interno).

    Credit card / PIX sem encoded_image: manda 1 mensagem texto (compat).
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
        .replace("{{payment_id}}", payment_id)
    )

    # Log estruturado do payload que o notify vai receber (rastreabilidade).
    # email/phone/name ficam no log mas NAO sao enviados no body — notify
    # resolve esses campos via lookup em `contact` pelo external_id. O log
    # serve pra auditar que o contact ja tem email/phone setados antes do
    # dispatch (se nao tiver, notify pula o canal).
    # `event` colide com a 1a posicional do structlog.info; renomeei
    # pra `notify_event` (semantic: nome do evento que sera enviado ao
    # notify), nao quebra estrutura do log mas evita TypeError.
    logger.info(
        "notify_dispatch_lead",
        notify_event="checkout_lead",
        payment_method=payment_method,
        external_id=external_id,
        payment_id=payment_id,
        email=email or None,
        phone=phone or None,
        name=first_name or None,
        has_pix_payload=bool(customer_link),
        has_qr_url=bool(qr_url),
        has_qr_image=bool(encoded_image_b64),
        due_date=due_date_iso,
        content_len=len(content),
    )

    is_pix = payment_method == "pix"

    # ── Etapa 1 — texto teaser (WhatsApp + Email, compat) ────────────────
    await _run_pix_step(
        step="whatsapp_text" if is_pix else "checkout_text",
        external_id=external_id,
        coro_factory=lambda: notify_and_track(
            external_id,
            content,
            event="checkout_lead",
        ),
    )

    # Sem QR (CC ou PIX fallback sem encoded_image) — flow termina aqui.
    if not (is_pix and encoded_image_b64):
        return

    # ── Etapa 2 — WhatsApp QR imagem + caption copia-e-cola ──────────────
    caption_template_path = MESSAGES / "checkout_lead_pix_qr.md"
    if caption_template_path.exists():
        caption = caption_template_path.read_text(encoding="utf-8").replace(
            "{{pix_payload}}",
            customer_link,
        )
    else:
        # Fallback: caption minimo com so o BR Code (copia-e-cola direto).
        caption = customer_link

    await _run_pix_step(
        step="whatsapp_image",
        external_id=external_id,
        coro_factory=lambda: notify_and_track(
            external_id,
            caption,
            media_url=make_data_uri(encoded_image_b64),
            title="QR Code PIX",
            event="checkout_lead_pix_qr",
            channels=["whatsapp"],
        ),
    )

    # ── Etapa 3 — Email dedicado "Seu PIX Supletivo Brasil" ──────────────
    email_template_path = MESSAGES / "checkout_lead_pix_email.md"
    if email_template_path.exists():
        email_template = email_template_path.read_text(encoding="utf-8")
    else:
        # Defensive: template sumiu do disco — degrade pra caption + payload.
        email_template = "# Seu PIX Supletivo Brasil\n\n{{pix_payload}}\n\n{{due_date_line}}\n"
    due_date_line = f"**Vencimento:** {due_date_iso}\n" if due_date_iso else ""
    email_body = (
        email_template.replace("{{pix_payload}}", customer_link)
        .replace("{{due_date_line}}", due_date_line)
        .replace("{{payment_id}}", payment_id)
    )

    await _run_pix_step(
        step="email",
        external_id=external_id,
        coro_factory=lambda: notify_and_track(
            external_id,
            email_body,
            media_url=make_data_uri(encoded_image_b64),
            title="Seu PIX Supletivo Brasil",
            event="checkout_lead_pix_email",
            channels=["email"],
        ),
    )


async def _run_pix_step(
    *,
    step: str,
    external_id: str,
    coro_factory,
) -> None:
    """Executa 1 etapa de notify_and_track com log `pix_notify_step` per-step.

    Cada etapa loga `pix_notify_step` (sucesso) ou `pix_notify_step_failed`
    (excecao) com external_id + step + status + message_id/erro. Nao re-raise:
    uma etapa falha nao deve impedir as proximas (decisao do prompt #4 do
    operador — sem retry; notify ja retenta WhatsApp internamente).
    """
    try:
        msg = await coro_factory()
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "pix_notify_step_failed",
            step=step,
            external_id=external_id,
            error=str(exc),
            error_type=type(exc).__name__,
        )
        return
    if msg is None:
        # notify_and_track engole HTTPStatusError e devolve None apos
        # persistir Message com status=failed/skipped — log explicito aqui
        # pra que cada etapa apareca no audit trail.
        logger.warning(
            "pix_notify_step",
            step=step,
            external_id=external_id,
            status="failed_or_skipped",
        )
        return
    logger.info(
        "pix_notify_step",
        step=step,
        external_id=external_id,
        status=msg.status,
        message_id=msg.message_id,
    )


async def _notify_promoter_checkout(
    external_id: str,
    phone: str,
    first_name: str,
    customer_link: str,
    qr_url: str,
    payment_id: str,
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
        .replace("{{payment_id}}", payment_id)
    )
    logger.info(
        "notify_dispatch_promoter",
        event="checkout_promoter",
        payment_method=payment_method,
        external_id=external_id,
        promoter_id=str(promoter_id),
        payment_id=payment_id,
        lead_phone=phone or None,
        lead_name=first_name or None,
        has_pix_payload=bool(customer_link),
        has_qr_url=bool(qr_url),
        has_qr_image=bool(encoded_image_b64),
        content_len=len(content),
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
