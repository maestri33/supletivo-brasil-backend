"""Envia mensagem via notify e persiste registro local para rastreabilidade.

Contrato com notify (fire-and-forget + webhook callback):
1. Lead chama POST /api/v1/messages/send com `webhook_url=NOTIFY_CALLBACK_URL`.
2. Notify devolve `message_id` IMEDIATAMENTE (background task processa entrega).
3. Lead registra lead.Message com `status="pending"` (NAO "sent" — ainda nao confirmou).
4. Quando notify termina (sucesso/falha), POST {NOTIFY_CALLBACK_URL}/{message_id}
   chega no /api/v1/webhook/notify/{message_id}, que atualiza o status real.

Por que NAO retry:
- POST /messages/send NAO E idempotente. Se o lead reta em timeout, cria
  uma SEGUNDA Message no notify (duplica entrega no WhatsApp).
- Notify ja faz retry interno do envio do WhatsApp (Evolution/Baileys) e
  e responsavel por reportar o resultado final via webhook.
- Se a chamada falha de cara (network), o lead registra `failed` e
  segue — sem retry. Eventual recovery e' via re-trigger da business logic.

Tratamento de falha:
- 404 do notify (contact nao seedado, ex.: promoter sem `notify.contacts`):
  log `notify_contact_not_seeded` + persiste Message com status=skipped.
- Outros erros: log `notify_send_failed` e Message com status=failed.
"""

from uuid import UUID

import httpx
import structlog

from app.config import settings
from app.db import async_session_maker
from app.integrations.notify import NotifyClient
from app.models import Message

logger = structlog.get_logger()


async def notify_and_track(
    external_id: str,
    content: str,
    *,
    channel: str = "whatsapp",
    instruction: str | None = None,
    event: str | None = None,
    media_url: str | None = None,
    title: str | None = None,
    flags: dict | None = None,
    channels: list[str] | None = None,
) -> Message | None:
    """Envia mensagem via notify e salva registro local com status=pending.

    `media_url` aceita URL HTTP publica OU data URI `data:image/png;base64,...`
    Notify cuida do upload/anexo no WhatsApp (vai como midia, caption=content).

    `channels` (opcional) restringe os canais de entrega no notify. None =
    ambos (whatsapp + email se contato tiver). ['whatsapp'] = so WhatsApp.
    ['email'] = so email. Quando explicito, o campo `channel` persistido no
    lead reflete a uniao (`whatsapp+email`, `whatsapp`, `email`).

    O status final (`sent`/`failed`) chega via webhook em
    /api/v1/webhook/notify/{message_id} — ate la, o registro fica `pending`.
    """
    log = logger.bind(external_id=external_id, event=event)
    if channels:
        channel = "+".join(sorted(channels))

    failure_status: str | None = None
    failure_event: str | None = None
    message_id: int | None = None

    # Log do payload exato que sera POSTado em /api/v1/messages/send.
    # Truncamos `content` no log (pode ter QR base64 ou markdown longo)
    # mas mantemos sinais binarios (media presence) e tamanho. Permite
    # auditar `Notify recebeu X` vs `Lead enviou Y` em outage de canal
    # (ex.: WhatsApp ok mas email vazio).
    log.info(
        "notify_send_request",
        url="/api/v1/messages/send",
        channel=channel,
        channels=channels,
        title=title,
        has_media=bool(media_url),
        media_kind=(
            "data_uri"
            if media_url and media_url.startswith("data:")
            else ("url" if media_url else None)
        ),
        flags=flags,
        instruction=instruction,
        content_len=len(content),
        content_preview=content[:200],
        webhook_url=settings.NOTIFY_CALLBACK_URL,
    )

    # Timeout curto: notify responde rapido (cria Message + BG task, ~100ms).
    # SEM retry aqui — POST /messages/send nao e idempotente; retry duplica
    # entregas no WhatsApp. O notify se vira via webhook callback.
    async with httpx.AsyncClient(
        base_url=settings.NOTIFY_BASE_URL,
        timeout=settings.HTTP_TIMEOUT,
    ) as http:
        notify = NotifyClient(http)
        try:
            await notify.send_message(
                external_id=external_id,
                content=content,
                instruction=instruction,
                media_url=media_url,
                title=title,
                flags=flags,
                channels=channels,
                webhook_url=settings.NOTIFY_CALLBACK_URL,
                max_retries=1,  # idempotency: sem retry no POST de envio
            )
            message_id = notify.last_message_id
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                log.warning(
                    "notify_contact_not_seeded",
                    status=404,
                    body=exc.response.text[:200],
                )
                failure_status = "skipped"
                failure_event = "contact_not_seeded"
            else:
                log.error(
                    "notify_send_failed",
                    status=exc.response.status_code,
                    body=exc.response.text[:200],
                )
                failure_status = "failed"
                failure_event = f"http_{exc.response.status_code}"
        except Exception as exc:
            log.error("notify_send_failed", error=str(exc))
            failure_status = "failed"
            failure_event = "exception"

    # `pending` ate o webhook callback chegar; `failed`/`skipped` ja sao finais.
    final_status = failure_status or "pending"
    final_event = failure_event or event

    async with async_session_maker() as session:
        msg = Message(
            message_id=message_id,
            external_id=UUID(external_id),
            direction="out",
            channel=channel,
            content=content,
            status=final_status,
            event=final_event,
        )
        session.add(msg)
        await session.commit()
        await session.refresh(msg)

    if failure_status is None:
        log.info("message_tracked", message_id=message_id, status="pending")
    return msg
