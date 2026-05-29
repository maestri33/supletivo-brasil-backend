"""Persistencia do QR Code PNG (base64 vindo do Asaas) em disco + URL absoluta.

Asaas devolve `pixQrCode.encodedImage` como string base64 sem prefixo `data:`.
Aqui decodificamos e gravamos como arquivo binario em
`{media_dir}/qrcodes/<payment_id>.png`, servido via StaticFiles em
`/api/v1/public/media/qrcodes/<payment_id>.png` (mount em main.py).

Chave de arquivo = `payment_id` (asaas-side). Anteriormente o `lead` salvava
o PNG localmente keyed por external_id; consolidamos no asaas porque ele e' o
dono natural do binario (mesma origem do `encodedImage`).
"""

from __future__ import annotations

import base64
from pathlib import Path

from ..config import get_settings
from ..utils.logging import log_event

_QR_SUBDIR = "qrcodes"
_PUBLIC_PREFIX = "/api/v1/public/media"


def _qr_dir() -> Path:
    d = Path(get_settings().media_dir) / _QR_SUBDIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_pix_qr_png(payment_id: str, encoded_image_b64: str) -> str:
    """Decodifica base64, grava o PNG e devolve a URL ABSOLUTA publica.

    Returns:
        URL absoluta (ex.: 'https://asaas.m33.live/api/v1/public/media/qrcodes/pay_abc.png')
        quando `ASAAS_PUBLIC_BASE_URL` esta setada. Caso contrario, URL relativa
        (so o path) — caller pode prefixar manualmente. Nao levantamos erro
        nessa branch porque dev/CI rodam sem base URL e ainda assim conseguem
        validar o pipeline.
    """
    try:
        png_bytes = base64.b64decode(encoded_image_b64, validate=True)
    except Exception as exc:
        log_event("qrcode_b64_decode_failed", payment_id=payment_id, error=str(exc))
        raise

    file_path = _qr_dir() / f"{payment_id}.png"
    file_path.write_bytes(png_bytes)
    log_event("qrcode_saved", payment_id=payment_id, path=str(file_path), bytes=len(png_bytes))

    relative = f"{_PUBLIC_PREFIX}/{_QR_SUBDIR}/{file_path.name}"
    base = get_settings().asaas_public_base_url
    if not base:
        return relative
    return f"{base.rstrip('/')}{relative}"


def absolute_qr_url_for(payment_id: str) -> str | None:
    """Reconstroi a URL publica a partir do payment_id (sem tocar disco).

    Util pra `to_dict()` em rows ja persistidas sem `pix_qr_url` armazenado
    (computed-on-read). Devolve None se `ASAAS_PUBLIC_BASE_URL` nao setada
    OU se o arquivo nao existe em disco (evita publicar URL morta).
    """
    base = get_settings().asaas_public_base_url
    if not base:
        return None
    file_path = _qr_dir() / f"{payment_id}.png"
    if not file_path.exists():
        return None
    return f"{base.rstrip('/')}{_PUBLIC_PREFIX}/{_QR_SUBDIR}/{file_path.name}"
