"""Orquestrador central de envio de mensagens (SQLAlchemy 2).

Fluxo:
  1. Resolve contacto por external_id
  2. Extrai texto (de .md ou direto)
  3. Detecta tipo de midia se houver (base64 ou URL)
  4. Se --ai, gera texto via AI service /text
  5. Se --img, gera imagem via AI service /image
  6. WhatsApp: *{title}*\n\n{text}  (com retry transient: 1s, 3s, 9s...)
  7. Prepara HTML email com {{title}} e {{content}}
  8. Envia Email
  9. Se --tts (so p/ texto), gera audio + envia WhatsApp voice note
 10. Atualiza statuses
"""

import asyncio
import html as _html
import mimetypes
import re
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import async_session_maker
from app.integrations.ai import AIClient
from app.integrations.mailcow import MailcowSMTPClient
from app.integrations.profiles import ProfilesClient
from app.integrations.whatsapp import WhatsAppClient
from app.models.log import Log
from app.models.message import (
    STATUS_FAILED,
    STATUS_SENT,
    STATUS_SKIPPED,
    Message,
)
from app.schemas.message import MessageSend, TestEmailRequest, TestEmailResult
from app.services import template_service
from app.services.contact_service import get_contact_by_external_id
from app.utils.logging import get_logger

log = get_logger(__name__)

_MIME_MAP = {
    "image/jpeg": "image", "image/jpg": "image", "image/png": "image",
    "image/webp": "image", "image/gif": "image",
    "video/mp4": "video", "video/quicktime": "video",
    "audio/mpeg": "audio", "audio/mp3": "audio", "audio/ogg": "audio",
    "audio/opus": "audio", "audio/wav": "audio",
}
_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
_VIDEO_EXT = {".mp4", ".mov", ".avi", ".mkv"}
_AUDIO_EXT = {".mp3", ".ogg", ".wav", ".opus", ".m4a"}


def _detect_media(source: str) -> tuple[str, str | None]:
    if source.startswith("data:"):
        m = re.match(r"data:([^;]+);", source)
        mime = m.group(1) if m else "application/octet-stream"
        return _MIME_MAP.get(mime, "document"), mime

    path = urlparse(source).path.lower()
    ext = "." + path.rsplit(".", 1)[-1] if "." in path else ""
    if ext in _IMAGE_EXT:
        return "image", mimetypes.types_map.get(ext)
    if ext in _VIDEO_EXT:
        return "video", mimetypes.types_map.get(ext)
    if ext in _AUDIO_EXT:
        return "audio", mimetypes.types_map.get(ext)
    return "document", mimetypes.types_map.get(ext)


def _public_url(relative_path: str) -> str:
    base = get_settings().public_base_url.rstrip("/")
    return f"{base}/media/{relative_path}"


def _dmz_url(relative_path: str) -> str:
    base = get_settings().dmz_base_url.rstrip("/")
    return f"{base}/media/{relative_path}"


def _handle_base64_media(data_uri: str) -> tuple[str, str, str, str]:
    """Decodifica data URI base64, salva em disco e devolve URLs + base64 puro.

    Returns:
        (public_url, dmz_url, media_type, pure_b64)

    O `pure_b64` (sem prefixo `data:`) e' o que devemos passar pra Evolution
    API no campo `media`. Evolution rejeita URLs HTTP internas com
    `"Owned media must be a url or base64"` (requer HTTPS ou base64 puro);
    `public_url`/`dmz_url` ficam pra outros canais (email HTML).
    """
    import base64 as b64
    import uuid

    m = re.match(r"data:([^;]+);base64,(.+)", data_uri, re.DOTALL)
    if not m:
        raise ValueError("Data URI invalida")
    mime = m.group(1)
    pure_b64 = m.group(2).strip()
    raw = b64.b64decode(pure_b64)

    media_type = _MIME_MAP.get(mime, "document")
    ext_map = {
        "image/jpeg": ".jpg", "image/jpg": ".jpg", "image/png": ".png",
        "image/webp": ".webp", "image/gif": ".gif",
        "video/mp4": ".mp4", "video/quicktime": ".mov",
        "audio/mpeg": ".mp3", "audio/mp3": ".mp3", "audio/ogg": ".ogg",
        "audio/opus": ".opus", "audio/wav": ".wav",
        "application/pdf": ".pdf",
    }
    ext = ext_map.get(mime, mimetypes.guess_extension(mime) or ".bin")
    filename = f"{uuid.uuid4().hex}{ext}"
    out = Path("media/imagem")
    out.mkdir(parents=True, exist_ok=True)
    (out / filename).write_bytes(raw)
    relative = f"imagem/{filename}"
    public_url = _public_url(relative)
    dmz_url = _dmz_url(relative)
    log.info(
        "media.base64_decoded", mime=mime, relative=relative, bytes=len(raw),
    )
    return public_url, dmz_url, media_type, pure_b64


def _email_media_html(media_url: str, media_type: str, caption: str) -> str:
    safe_url = _html.escape(media_url)
    safe_caption = _html.escape(caption)

    if media_type == "image":
        return (
            f'<div style="margin:20px 0;text-align:center">'
            f'<img src="{safe_url}" alt="{safe_caption}" '
            f'style="max-width:100%;height:auto;border-radius:4px">'
            f'<p style="margin:8px 0 0;color:#666;font-size:14px;font-family:Arial,sans-serif">'
            f'{safe_caption}</p>'
            f'</div>'
        )
    if media_type == "video":
        return (
            f'<div style="margin:20px 0;text-align:center">'
            f'<p style="font-size:40px;margin:0">&#9654;&#65039;</p>'
            f'<p style="margin:8px 0;font-family:Arial,sans-serif;font-size:15px;color:#333">{safe_caption}</p>'
            f'<a href="{safe_url}" target="_blank" '
            f'style="color:#1a73e8;font-family:Arial,sans-serif;font-size:14px">Assistir v&iacute;deo</a>'
            f'</div>'
        )
    if media_type == "audio":
        return (
            f'<div style="margin:20px 0;text-align:center">'
            f'<p style="font-size:36px;margin:0">&#127911;</p>'
            f'<p style="margin:8px 0;font-family:Arial,sans-serif;font-size:15px;color:#333">{safe_caption}</p>'
            f'<a href="{safe_url}" target="_blank" '
            f'style="color:#1a73e8;font-family:Arial,sans-serif;font-size:14px">Ouvir &aacute;udio</a>'
            f'</div>'
        )
    safe_name = _html.escape(media_url.rsplit("/", 1)[-1] if "/" in media_url else "arquivo")
    return (
        f'<div style="margin:20px 0;text-align:center">'
        f'<p style="font-size:36px;margin:0">&#128206;</p>'
        f'<p style="margin:4px 0;font-family:Arial,sans-serif;font-size:13px;color:#666">{safe_name}</p>'
        f'<p style="margin:8px 0;font-family:Arial,sans-serif;font-size:15px;color:#333">{safe_caption}</p>'
        f'<a href="{safe_url}" target="_blank" '
        f'style="color:#1a73e8;font-family:Arial,sans-serif;font-size:14px">Baixar arquivo</a>'
        f'</div>'
    )


def _extract_title(text: str, fallback: str = "Nova mensagem") -> str:
    m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    if m:
        return m.group(1).strip()[:120]
    return fallback


def _resolve_title(payload: MessageSend) -> str:
    if payload.title:
        return payload.title
    return _extract_title(payload.content)


def _strip_leading_h1(text: str, title: str) -> str:
    """Remove a primeira linha '# <title>' do markdown se ela bater com o title.

    Quando o caller monta o WhatsApp como `*{title}*\\n\\n{content}` e tambem
    inclui '# {title}' na primeira linha do markdown, o destinatario ve o
    titulo DUAS vezes (uma como bold prepend, outra como cabecalho markdown).
    Mesmo problema no email (template renderiza title no header E content
    no body). Esta funcao normaliza: se o markdown comeca com '# X' e X bate
    com title (ou title foi extraido daquela linha), remove o '# X' + uma
    linha em branco subsequente. Preserva H1s que nao sejam o titulo (raro).
    """
    pattern = r"^#\s+" + re.escape(title.strip()) + r"\s*\n+"
    return re.sub(pattern, "", text, count=1, flags=re.MULTILINE).lstrip()


def _md_bold_to_whatsapp(text: str) -> str:
    """Converte '**texto**' (markdown CommonMark) em '*texto*' (WhatsApp).

    WhatsApp suporta apenas asterisco unico para bold. Se mandarmos '**X**',
    o WhatsApp interpreta o primeiro par como bold e mostra o segundo
    asterisco literal — resultado visual: '*X*' com asterisco extra
    confuso. Esta funcao normaliza ANTES do send_text/caption.
    """
    return re.sub(r"\*\*(.+?)\*\*", r"*\1*", text, flags=re.DOTALL)


def _md_bold_to_html_after_escape(text: str) -> str:
    """Converte bold markdown em '<strong>...</strong>' DEPOIS de html.escape.

    Suporta DUAS sintaxes:
      - '**texto**' (Markdown CommonMark)
      - '*texto*'   (WhatsApp/Telegram style — alguns templates usam pra
                     manter consistencia visual entre canais)

    Ordem importa: **X** primeiro (especifico), depois *X* (geral). O padrao
    '\\*([^*\\s].*?[^*\\s]|[^*\\s])\\*' garante que aberta/fecha em palavra
    (sem espaco/asterisco) — evita falsos positivos em '5 * 5 = 25' ou
    listas tipo '* item'.

    O `_render_html` escapa o content antes pra evitar XSS; os asteriscos
    sobrevivem ao escape, entao a conversao aqui e' segura."""
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text, flags=re.DOTALL)
    text = re.sub(
        r"(?<![*\w])\*([^*\s](?:.*?[^*\s])?)\*(?![*\w])",
        r"<strong>\1</strong>",
        text,
        flags=re.DOTALL,
    )
    return text


def _render_html(
    template: str,
    title: str,
    content: str,
    *,
    content_is_html: bool = False,
) -> str:
    """Renderiza o template substituindo `{{title}}`, `{{content}}` e
    `{{service_name}}`.

    `content_is_html=True` quando o caller ja' montou HTML (ex.: snippet
    de `<img src=...>` por `_email_media_html`). Sem isso, `_html.escape`
    transformaria as tags em texto literal (`&lt;img&gt;`) e o email
    chegaria visualmente quebrado.
    """
    settings = get_settings()
    safe_title = _html.escape(title)
    if content_is_html:
        safe_content = content  # ja' e' HTML montado e validado pelo caller
    else:
        # Escape primeiro (XSS-safe), depois aplica markdown bold sobre o
        # texto ja escapado. '**texto**' sobrevive ao escape e vira tag
        # <strong> de forma segura. Newlines em <br> mantem layout.
        safe_content = _md_bold_to_html_after_escape(
            _html.escape(content)
        ).replace("\n", "<br>")
    return (
        template.replace("{{title}}", safe_title)
        .replace("{{content}}", safe_content)
        .replace("{{service_name}}", _html.escape(settings.service_name))
    )


# ── Retry helper (WhatsApp send transient errors) ──────────────────────────


def _is_retryable(exc: BaseException) -> bool:
    """Heuristica: retentamos erros transitorios HTTP (5xx, timeout, conn reset).

    Erros que indicam config errada (auth, 4xx) NAO sao retentados — apenas
    consomem tempo sem mudar resultado.
    """
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    msg = str(exc).lower()
    return any(
        marker in msg
        for marker in ("timeout", "connection", "reset", "temporarily", "503", "502", "500")
    )


async def _retry(
    label: str,
    fn: Callable[[], Awaitable[Any]],
    *,
    max_retries: int,
    backoff_base_s: float,
) -> tuple[Any, int, str | None]:
    """Executa `fn` ate sucesso ou esgotar tentativas com backoff exponencial.

    Retorna `(resultado_ou_None, tentativas_executadas, ultimo_erro_str)`.
    Sucesso: `(result, n, None)`. Falha persistente: `(None, n, "<erro>")`.

    Levanta APENAS se a primeira tentativa der erro nao-retryable (config
    error, validation, etc.) — assim chamadores ainda podem distinguir
    "transient esgotado" vs "erro permanente logo de cara".
    """
    last_exc: BaseException | None = None
    for attempt in range(1, max_retries + 2):  # max_retries=3 -> 4 tentativas (1 + 3 retries)
        try:
            return await fn(), attempt, None
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if not _is_retryable(exc):
                log.warning(
                    f"{label}.non_retryable", attempt=attempt, error=str(exc)[:200],
                )
                return None, attempt, str(exc)
            if attempt > max_retries:
                break
            sleep_s = backoff_base_s * (3 ** (attempt - 1))
            log.info(
                f"{label}.retry", attempt=attempt, sleep_s=sleep_s, error=str(exc)[:200],
            )
            await asyncio.sleep(sleep_s)
    return None, attempt, str(last_exc) if last_exc else "unknown"


# ── DB operations ──────────────────────────────────────────────────────────


async def list_messages(
    session: AsyncSession,
    contact_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Message]:
    stmt = select(Message)
    if contact_id is not None:
        stmt = stmt.where(Message.contact_id == contact_id)
    result = await session.scalars(stmt.offset(offset).limit(limit))
    return list(result.all())


async def get_message(session: AsyncSession, message_id: int) -> Message | None:
    return await session.get(Message, message_id)


async def send_message(session: AsyncSession, payload: MessageSend) -> Message:
    """Cria a mensagem com status 'pending' (processamento em background)."""
    contact = await get_contact_by_external_id(session, payload.external_id)

    message = Message(
        contact_id=contact.id,
        type="text",
        content_text=payload.content,
    )
    session.add(message)
    await session.flush()  # garante message.id antes do Log

    session.add(
        Log(
            message_id=message.id,
            external_id=contact.external_id,
            action="message.created",
            details={
                "contact_external_id": str(payload.external_id),
                "title": payload.title,
                "template_slug": payload.template_slug,
                "flags": payload.flags.model_dump(),
                "has_webhook": bool(payload.webhook_url),
            },
        )
    )
    await session.commit()
    await session.refresh(message)
    log.info("message.created", id=message.id, external_id=str(payload.external_id))
    return message


async def process_message(payload: MessageSend, message_id: int) -> None:
    """Processa uma mensagem em background: AI, WhatsApp, Email, TTS, webhook.

    Roda fora do request — abre sua própria session.
    """
    settings = get_settings()
    async with async_session_maker() as session:
        contact = await get_contact_by_external_id(session, payload.external_id)
        message = await session.get(Message, message_id)
        if not message:
            log.error("message.not_found_for_processing", id=message_id)
            return

        async with httpx.AsyncClient() as http:
            text = payload.content
            if text.startswith(("http://", "https://")) and text.endswith(".md"):
                try:
                    resp = await http.get(text, timeout=15.0)
                    resp.raise_for_status()
                    text = resp.text
                except Exception as exc:
                    log.error("md_download_failed", url=text, error=str(exc))

            media_type = None
            media_url = payload.media_url
            whatsapp_media_url: str | None = None
            email_media_url: str | None = None
            # Bytes da imagem p/ CID inline embed no email (vide MIME
            # multipart/related em MailcowSMTPClient.send_email).
            inline_email_images: dict[str, tuple[bytes, str]] = {}

            if payload.media_url:
                if payload.media_url.startswith("data:"):
                    # Para WhatsApp passamos o base64 PURO (sem prefixo data:);
                    # a Evolution API rejeita URLs HTTP internas com
                    # "Owned media must be a url or base64".
                    media_url, _dmz_unused, media_type, _wa_b64 = _handle_base64_media(
                        payload.media_url
                    )
                    whatsapp_media_url = _wa_b64
                    # Pra email: tambem embute via CID se for imagem (QR PIX,
                    # comprovantes, etc). Sem isso o email vira so texto +
                    # caption, sem a imagem que o usuario espera.
                    if media_type == "image":
                        import base64 as _b64
                        try:
                            img_bytes = _b64.b64decode(_wa_b64, validate=True)
                            # Detecta subtype do data URI header (default jpeg).
                            mime_prefix = payload.media_url.split(",", 1)[0]
                            subtype = "jpeg"
                            if "/" in mime_prefix:
                                m = re.search(r"image/(\w+)", mime_prefix)
                                if m:
                                    subtype = m.group(1)
                            cid = "notify-img-1"
                            inline_email_images[cid] = (img_bytes, subtype)
                            email_media_url = f"cid:{cid}"
                        except Exception as exc:
                            log.warning("inline_email_img_decode_failed", error=str(exc))
                else:
                    media_type, _ = _detect_media(payload.media_url)

            msg_type = "media" if media_type else "text"
            tts_enabled = payload.flags.tts and msg_type == "text"

            ai = AIClient(http)
            ai_used = False
            if payload.flags.ai and msg_type == "text":
                ai_used = True
                try:
                    text = await ai.text(prompt=text, instruction=payload.instruction)
                    log.info("ai.text_generated", length=len(text))
                    if "{{" in text:
                        text = re.sub(r"\{\{.*?\}\}", "", text).strip()
                except Exception as exc:
                    log.error("ai.generation_failed", error=str(exc))

            img_used = False

            if payload.flags.img:
                img_used = True
                try:
                    import base64 as _b64

                    ref_url = media_url if media_type == "image" else None
                    prompt = f"{payload.instruction} | {text}" if payload.instruction else text
                    result = await ai.image(prompt=prompt, reference_url=ref_url)
                    # WhatsApp: Evolution 2.3.7 rejeita URLs HTTP internas e
                    # publicas tipo `ai.m33.live`. notify baixa via URL
                    # interna docker e passa base64 puro pro Evolution.
                    internal_url = (
                        f"{settings.ai_base_url.rstrip('/')}"
                        f"/media/image/{result['filename']}"
                    )
                    dl = await http.get(internal_url, timeout=30.0)
                    dl.raise_for_status()
                    whatsapp_media_url = _b64.b64encode(dl.content).decode("ascii")

                    # Email: CID inline embed em vez de URL publica
                    # `ai.m33.live` (NXDOMAIN em DNS publico — Gmail
                    # renderiza icone de imagem quebrada). Reusa os bytes
                    # ja baixados.
                    mime = result.get("mime_type") or "image/jpeg"
                    subtype = mime.split("/", 1)[-1] if "/" in mime else "jpeg"
                    cid = "notify-img-1"
                    inline_email_images[cid] = (dl.content, subtype)
                    email_media_url = f"cid:{cid}"

                    media_type = "image"
                    msg_type = "media"
                    tts_enabled = False
                    log.info(
                        "img.generated",
                        bytes=len(dl.content), mime=mime,
                        public_url=result["url"],
                    )
                except Exception as exc:  # noqa: BLE001
                    log.error("img.generation_failed", error=str(exc)[:200])

            message.type = msg_type
            message.content_text = text

            title = _resolve_title(payload)
            # Strip do '# {title}' que veio no markdown — o WhatsApp prepende
            # '*{title}*\n\n' e o email render usa o title no header. Sem o
            # strip, o destinatario ve o titulo DUAS vezes.
            stripped = _strip_leading_h1(text, title)

            # WhatsApp suporta apenas '*bold*' (asterisco unico). Markdown
            # CommonMark '**bold**' fica visualmente quebrado no WhatsApp
            # ('*bold*' com asteriscos extras visiveis). Convertemos pre-send.
            # Email recebe o markdown cru e o _render_html cuida da conversao
            # pra <strong> apos o html.escape.
            body = _md_bold_to_whatsapp(stripped)

            template = await template_service.get_active_or_default(
                session, payload.template_slug,
            )
            _email_url = email_media_url if img_used or email_media_url else media_url
            has_media_html = bool(media_type and _email_url)
            email_body = (
                _email_media_html(_email_url, media_type, stripped)
                if has_media_html
                else stripped
            )
            html = _render_html(
                template.html, title, email_body,
                content_is_html=has_media_html,
            )

            whatsapp = WhatsAppClient(http)
            _wa_url = whatsapp_media_url or media_url
            whatsapp_attempts = 0
            whatsapp_error: str | None = None
            tts_failed = False
            tts_fallback_reason: str | None = None
            if contact.phone:
                # Resolve a variante BR (com/sem nono digito) que esta
                # efetivamente registrada no WhatsApp. Sem isso, Evolution
                # 2.3.7 normaliza errado (perde o 9°) e entrega silenciosa.
                # Cache em memoria 1h evita HTTP extra em sends repetidos.
                wa_number = await whatsapp.resolve_br_number(contact.phone)
                if not tts_enabled:
                    # Usa `_wa_url` (que recebe base64 do img/payload base64
                    # ou URL original). A versao anterior checava `media_url`
                    # crua do payload, que era None quando img=true sem
                    # media_url no body — fazia o send_media nunca disparar
                    # e a mensagem caia no fallback de texto.
                    if media_type and _wa_url:
                        _, whatsapp_attempts, whatsapp_error = await _retry(
                            "whatsapp.send_media",
                            lambda: whatsapp.send_media(
                                wa_number, _wa_url, media_type, caption=body,
                            ),
                            max_retries=settings.whatsapp_max_retries,
                            backoff_base_s=settings.whatsapp_retry_backoff_base_s,
                        )
                    else:
                        full_text = f"*{title}*\n\n{body}"
                        _, whatsapp_attempts, whatsapp_error = await _retry(
                            "whatsapp.send_text",
                            lambda: whatsapp.send_text(wa_number, full_text),
                            max_retries=settings.whatsapp_max_retries,
                            backoff_base_s=settings.whatsapp_retry_backoff_base_s,
                        )
                    message.whatsapp_status = (
                        STATUS_SENT if whatsapp_error is None else STATUS_FAILED
                    )
                    if whatsapp_error:
                        log.error(
                            "whatsapp.send_failed",
                            attempts=whatsapp_attempts, error=whatsapp_error[:200],
                        )

                if tts_enabled:
                    # Pipeline TTS: gera audio + envia base64. Fallback
                    # graceful para texto se qualquer passo falhar.
                    #
                    # Evolution 2.3.7 rejeita URLs HTTP internas
                    # ("Owned media must be a url, base64, or valid file
                    # with buffer"). Estrategia: notify baixa o audio do
                    # `ai` via URL interna docker (`http://ai:8000/media/
                    # audio/<filename>`) e passa base64 puro pro Evolution.

                    # Resolve voz por genero antes do TTS. Falha silenciosa
                    # (profile 404, gender None, profiles down) -> voice_id
                    # = None -> AI usa elevenlabs_voice_id default.
                    profiles_client = ProfilesClient(http)
                    gender = await profiles_client.get_gender(
                        str(payload.external_id)
                    )
                    tts_voice_id: str | None = None
                    if gender == "M":
                        tts_voice_id = settings.elevenlabs_voice_male
                    elif gender == "F":
                        tts_voice_id = settings.elevenlabs_voice_female
                    log.info(
                        "tts.voice_resolved",
                        external_id=str(payload.external_id),
                        gender=gender,
                        voice_id=tts_voice_id,
                    )

                    wa_audio_b64: str | None = None
                    try:
                        import base64 as _b64

                        # TTS: monta '<title>. <body_sem_H1>' pra que a fala
                        # comece pela saudacao do titulo (que foi strippada
                        # do body pra evitar duplicacao no texto WhatsApp/
                        # email, mas e' o gancho de abertura do audio).
                        # Asteriscos do markdown bold sao removidos pra
                        # evitar leitura literal pelo ElevenLabs.
                        clean_body = re.sub(r"\*+", "", body).strip()
                        tts_text = f"{title.rstrip('.!? ')}. {clean_body}"
                        result = await ai.tts(tts_text, voice_id=tts_voice_id)
                        filename = result["filename"]
                        internal_url = (
                            f"{settings.ai_base_url.rstrip('/')}"
                            f"/media/audio/{filename}"
                        )
                        dl = await http.get(internal_url, timeout=30.0)
                        dl.raise_for_status()
                        wa_audio_b64 = _b64.b64encode(dl.content).decode("ascii")
                        message.tts_audio_url = result["url"]  # publica p/ audit
                        log.info(
                            "tts.audio_ready",
                            filename=filename, bytes=len(dl.content),
                        )
                    except Exception as exc:  # noqa: BLE001
                        log.error("tts.generation_failed", error=str(exc)[:200])
                        tts_failed = True
                        tts_fallback_reason = f"generation: {type(exc).__name__}"

                    if not tts_failed and wa_audio_b64:
                        _, whatsapp_attempts, whatsapp_error = await _retry(
                            "whatsapp.send_audio",
                            lambda: whatsapp.send_whatsapp_audio(
                                wa_number, wa_audio_b64,
                            ),
                            max_retries=settings.whatsapp_max_retries,
                            backoff_base_s=settings.whatsapp_retry_backoff_base_s,
                        )
                        if whatsapp_error is None:
                            message.whatsapp_status = STATUS_SENT
                            log.info(
                                "tts.sent",
                                contact=str(payload.external_id),
                                attempts=whatsapp_attempts,
                            )
                        else:
                            log.error(
                                "tts.send_failed",
                                attempts=whatsapp_attempts,
                                error=whatsapp_error[:200],
                            )
                            tts_failed = True
                            tts_fallback_reason = (
                                f"send_audio: {whatsapp_error[:80]}"
                            )

                    if tts_failed:
                        # Fallback: envia texto normal no WhatsApp.
                        log.info(
                            "tts.fallback_to_text",
                            contact=str(payload.external_id),
                            reason=tts_fallback_reason,
                        )
                        full_text = f"*{title}*\n\n{body}"
                        _, whatsapp_attempts, whatsapp_error = await _retry(
                            "whatsapp.send_text_fallback",
                            lambda: whatsapp.send_text(wa_number, full_text),
                            max_retries=settings.whatsapp_max_retries,
                            backoff_base_s=settings.whatsapp_retry_backoff_base_s,
                        )
                        message.whatsapp_status = (
                            STATUS_SENT
                            if whatsapp_error is None
                            else STATUS_FAILED
                        )
                        if whatsapp_error:
                            log.error(
                                "whatsapp.fallback_send_failed",
                                attempts=whatsapp_attempts,
                                error=whatsapp_error[:200],
                            )
            else:
                message.whatsapp_status = STATUS_SKIPPED

            if contact.email:
                # Envio direto via Mailcow SMTP (STARTTLS 587). Substitui
                # o service `mail` Docker (que conflitava credenciais via
                # configure_smtp e mascarava 535 como ReadTimeout).
                try:
                    mc = MailcowSMTPClient()
                    await mc.send_email(
                        to_email=contact.email,
                        subject=title,
                        html_body=html,
                        plain_body=text,
                        inline_images=inline_email_images or None,
                    )
                    message.email_status = STATUS_SENT
                except Exception as exc:  # noqa: BLE001
                    log.error(
                        "email.send_failed",
                        error=f"{type(exc).__name__}: {exc!r}"[:300],
                    )
                    message.email_status = STATUS_FAILED
            else:
                message.email_status = STATUS_SKIPPED

        message.email_subject = title

        session.add(
            Log(
                message_id=message.id,
                external_id=contact.external_id,
                action="message.sent",
                details={
                    "contact_external_id": str(payload.external_id),
                    "type": msg_type, "media": media_type,
                    "whatsapp": message.whatsapp_status, "email": message.email_status,
                    "tts": tts_enabled, "ai": ai_used, "img": img_used,
                    "template_slug": template.slug,
                    "template_version": template.version,
                    "whatsapp_attempts": whatsapp_attempts or None,
                    "whatsapp_error": whatsapp_error,
                    "tts_fallback": tts_failed if tts_enabled else None,
                    "tts_fallback_reason": tts_fallback_reason,
                },
            )
        )
        await session.commit()
        log.info(
            "message.processed", id=message.id, type=msg_type,
            whatsapp=message.whatsapp_status, email=message.email_status,
        )

    if payload.webhook_url:
        wh_url = f"{payload.webhook_url.rstrip('/')}/{message_id}"
        try:
            async with httpx.AsyncClient() as http:
                wh_resp = await http.post(wh_url, json={
                    "event": "message.processed",
                    "message_id": message_id,
                    "contact_id": contact.id,
                    "external_id": str(payload.external_id),
                    "type": msg_type,
                    "whatsapp_status": message.whatsapp_status,
                    "email_status": message.email_status,
                    "email_subject": title,
                    "tts_audio_url": message.tts_audio_url,
                }, timeout=10.0)
                log.info("webhook.sent", url=wh_url, status=wh_resp.status_code)
        except Exception as exc:
            log.error("webhook.failed", url=wh_url, error=str(exc))


# ── Email de teste (mail-tester etc) — nao persiste Message nem Contact ────


async def send_test_email(
    session: AsyncSession, payload: TestEmailRequest,
) -> TestEmailResult:
    """Dispara um email de diagnostico sem criar Contact/Message.

    Registra Log `email.test_sent` (sucesso) ou `email.test_failed` (erro)
    para que o operador veja na timeline de logs.
    """
    template = await template_service.get_active_or_default(session, payload.template_slug)
    html = _render_html(template.html, payload.title, payload.content)

    smtp_response: dict | None = None
    error: str | None = None
    try:
        mc = MailcowSMTPClient()
        smtp_response = await mc.send_email(
            to_email=payload.to_email,
            subject=payload.title,
            html_body=html,
            plain_body=payload.content,
        )
        sent = True
        log.info(
            "email.test_sent",
            to=payload.to_email,
            template_slug=template.slug,
            template_version=template.version,
        )
    except Exception as exc:  # noqa: BLE001
        sent = False
        error = f"{type(exc).__name__}: {exc!r}"
        log.error("email.test_failed", to=payload.to_email, error=error[:300])

    session.add(
        Log(
            action="email.test_sent" if sent else "email.test_failed",
            details={
                "to_email": payload.to_email,
                "template_slug": template.slug,
                "template_version": template.version,
                "smtp_response": smtp_response,
                "error": error,
            },
        )
    )
    await session.commit()

    return TestEmailResult(
        sent=sent,
        to_email=payload.to_email,
        template_slug=template.slug,
        template_version=template.version,
        smtp_response=smtp_response,
        error=error,
    )
