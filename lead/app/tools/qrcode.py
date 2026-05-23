"""Persiste o QR Code PNG (base64 vindo do asaas) em disco e devolve a URL.

O Asaas retorna `pix.encoded_image` como string base64 sem prefixo data:.
Aqui decodificamos uma vez e gravamos como arquivo binario para servir via
StaticFiles em `/api/v1/public/media/qrcodes/<external_id>.png`.

O prefixo `/api/v1/public/*` casa com o matcher do Caddy listener publico
(:8081), entao a URL absoluta funciona via Tailscale Funnel / dominio publico
sem precisar de regra nova no proxy.
"""

import base64
from pathlib import Path

import structlog

from app.config import settings

logger = structlog.get_logger()

_QR_SUBDIR = "qrcodes"
_PUBLIC_PREFIX = "/api/v1/public/media"
# Prefixo legado usado antes de mover o mount para /api/v1/public/media.
# Registros antigos no DB ainda guardam URLs com este prefixo.
_LEGACY_PREFIX = "/media"


def _qr_dir() -> Path:
    d = Path(settings.MEDIA_DIR) / _QR_SUBDIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_pix_qr_png(external_id: str, encoded_image_b64: str) -> str:
    """Decodifica base64 e grava como PNG. Retorna a URL relativa publica.

    Returns:
        URL relativa pronta para uso (ex.: '/api/v1/public/media/qrcodes/<uuid>.png').
        Quem montar uma URL absoluta deve prefixar com `settings.LEAD_PUBLIC_BASE_URL`.
    """
    log = logger.bind(external_id=external_id)
    try:
        png_bytes = base64.b64decode(encoded_image_b64, validate=True)
    except Exception as exc:
        log.warning("qrcode_b64_decode_failed", error=str(exc))
        raise

    file_path = _qr_dir() / f"{external_id}.png"
    file_path.write_bytes(png_bytes)
    log.info("qrcode_saved", path=str(file_path), bytes=len(png_bytes))

    return f"{_PUBLIC_PREFIX}/{_QR_SUBDIR}/{file_path.name}"


def make_data_uri(encoded_image_b64: str, mime: str = "image/png") -> str:
    """Monta um data URI base64 para enviar como `media_url` ao notify.

    Notify aceita `data:` URIs em `media_url` — nessa forma, o WhatsApp
    recebe a IMAGEM ANEXADA (nao um link de texto). O `content` da mensagem
    vira o caption abaixo da imagem.
    """
    # Asaas devolve o base64 puro sem prefixo data:; concatenamos aqui.
    return f"data:{mime};base64,{encoded_image_b64}"


def absolute_qr_url(relative_url: str) -> str:
    """Prefixa a URL com `LEAD_PUBLIC_BASE_URL` quando o caller precisa
    de uma URL absoluta (ex.: para incluir em mensagens WhatsApp).

    Backwards-compat: registros antigos guardam '/media/qrcodes/<eid>.png'.
    Reescrevemos pro prefixo publico atual antes de montar a URL.
    """
    if relative_url.startswith(f"{_LEGACY_PREFIX}/"):
        relative_url = _PUBLIC_PREFIX + relative_url[len(_LEGACY_PREFIX):]
    base = settings.LEAD_PUBLIC_BASE_URL.rstrip("/")
    return f"{base}{relative_url}"
