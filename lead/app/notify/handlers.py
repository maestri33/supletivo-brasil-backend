import asyncio
from pathlib import Path

import httpx
import structlog

from app.config import settings
from app.tools.messaging import notify_and_track

logger = structlog.get_logger()
NOTIFY_DIR = Path(__file__).resolve().parent / "messages"


async def notify_lead_captured(external_id: str):
    """Aguarda auth criar o contact no notify e envia mensagem de boas-vindas.

    Polling configuravel via `LEAD_CONTACT_POLL_TIMEOUT_S` e
    `LEAD_CONTACT_POLL_INTERVAL_S`. Em caso de timeout, persiste uma
    Message com `status=skipped` para audit trail (em vez de falha silenciosa).

    Envio: TTS (audio + texto fallback). Profiles eh consultado em paralelo
    com o polling do contact pra resolver `first_name`; se profile demora
    mais que o contact, usa 'Querido(a)' como fallback.
    """
    template = (NOTIFY_DIR / "lead_captured.md").read_text(encoding="utf-8")
    log = logger.bind(external_id=external_id)

    interval = max(1, settings.LEAD_CONTACT_POLL_INTERVAL_S)
    total = max(2, settings.LEAD_CONTACT_POLL_TIMEOUT_S)
    max_attempts = max(1, total // interval)

    found = False
    async with httpx.AsyncClient(base_url=settings.NOTIFY_BASE_URL) as client:
        for attempt in range(1, max_attempts + 1):
            await asyncio.sleep(interval)
            try:
                r = await client.get(f"/api/v1/contacts/{external_id}")
                if r.is_success:
                    log.info(
                        "lead_contact_ready",
                        attempt=attempt,
                        max_attempts=max_attempts,
                    )
                    found = True
                    break
            except Exception as exc:
                log.debug("lead_contact_poll_error", attempt=attempt, error=str(exc))
            if attempt % 10 == 0:
                log.info(
                    "lead_contact_polling",
                    attempt=attempt,
                    max_attempts=max_attempts,
                    interval_s=interval,
                )

    # Resolve first_name (profile pode nao estar pronto se CPFHub falhou —
    # usa fallback amigavel pra nao quebrar a mensagem).
    first_name = ""
    try:
        async with httpx.AsyncClient(base_url=settings.PROFILES_BASE_URL) as client:
            r = await client.get(f"/api/v1/profiles/first-name/{external_id}")
            if r.is_success:
                first_name = r.json().get("first_name", "")
    except Exception as exc:
        log.warning("first_name_failed", error=str(exc))
    name = first_name or "Querido(a)"
    content = template.replace("{{first_name}}", name)

    if not found:
        log.warning(
            "lead_contact_timeout",
            max_attempts=max_attempts,
            timeout_s=total,
        )
        # Persiste audit trail: lead capturado mas mensagem skipped por contact ausente.
        await notify_and_track(
            external_id,
            content,
            event="lead_captured_timeout",
        )
        return

    # `flags={tts: true}` faz notify gerar audio ElevenLabs (voz F/M pelo
    # perfil) e enviar como voice note no WhatsApp. Fallback automatico pra
    # texto se TTS falhar. Email recebe a versao texto sempre.
    await notify_and_track(
        external_id,
        content,
        flags={"tts": True},
        event="lead_captured",
    )


async def notify_promoter_captured(external_id: str, phone: str, promoter_id: str):
    """Busca first_name do lead e notifica o promoter.

    Pula quando promoter_id e' o sentinel '00000000-...' (lead organico/sem
    indicacao). Sem isso, notify_and_track tenta INSERT em lead.messages com
    external_id sentinel e viola FK em auth.users (que so contem UUIDs reais).
    """
    log = logger.bind(external_id=external_id, promoter_id=promoter_id)

    if not promoter_id or promoter_id == "00000000-0000-0000-0000-000000000000":
        log.info("promoter_captured_skipped_sentinel")
        return

    template = (NOTIFY_DIR / "promoter_captured.md").read_text(encoding="utf-8")

    first_name = ""
    try:
        async with httpx.AsyncClient(base_url=settings.PROFILES_BASE_URL) as client:
            r = await client.get(f"/api/v1/profiles/first-name/{external_id}")
            if r.is_success:
                first_name = r.json().get("first_name", "")
    except Exception as exc:
        log.warning("first_name_failed", error=str(exc))

    content = template.replace("{{first_name}}", first_name or "Alguem").replace("{{phone}}", phone)

    await notify_and_track(promoter_id, content, event="promoter_captured")


async def notify_lead_completed(
    external_id: str,
    receipt_url: str,
    *,
    capture_method: str | None = None,
    installments: int | None = None,
    amount_cents: int | None = None,
):
    """Envia parabens + recibo ao lead apos pagamento.

    `amount_cents` e o valor em centavos:
      - InfinitePay envia `paid_amount` (centavos) no webhook
      - Asaas envia `value` em reais (decimal) — converter para centavos antes
        de chamar esta funcao (multiplicar por 100 e arredondar).
    """
    log = logger.bind(external_id=external_id)

    first_name = ""
    try:
        async with httpx.AsyncClient(base_url=settings.PROFILES_BASE_URL) as client:
            r = await client.get(f"/api/v1/profiles/first-name/{external_id}")
            if r.is_success:
                first_name = r.json().get("first_name", "")
    except Exception as exc:
        log.warning("first_name_failed", error=str(exc))

    name = first_name or "Querido(a)"

    tpl_completed = (NOTIFY_DIR / "lead_completed.md").read_text(encoding="utf-8")
    content_completed = tpl_completed.replace("{{name}}", name)

    await notify_and_track(
        external_id,
        content_completed,
        flags={"tts": True},
        event="lead_completed",
    )

    # Formatar valor BRL: 500 centavos -> "R$ 5,00"
    if amount_cents is not None and amount_cents > 0:
        amount_str = f"R$ {amount_cents / 100:.2f}".replace(".", ",")
    else:
        amount_str = "—"

    # Template por payment_method:
    #   PIX  -> nao tem receipt_url (Asaas nao emite recibo PIX) e parcelas
    #           e' sempre 1 (omitido pra evitar ruido).
    #   CC   -> tem receipt_url (InfinitePay) e parcelas pode ser >1.
    is_pix = (capture_method or "pix").lower() == "pix"
    tpl_name = "lead_receipt_pix.md" if is_pix else "lead_receipt_cc.md"
    tpl_receipt = (NOTIFY_DIR / tpl_name).read_text(encoding="utf-8")

    # Linha de parcelas (so CC, so se >1 — `em 1x` e' redundante):
    inst = installments or 1
    installments_line = f" em {inst}x" if (not is_pix and inst > 1) else ""

    content_receipt = (
        tpl_receipt.replace("{{amount}}", amount_str)
        .replace("{{installments_line}}", installments_line)
        .replace("{{receipt_url}}", receipt_url or "")
    )

    await notify_and_track(external_id, content_receipt, event="lead_receipt")
