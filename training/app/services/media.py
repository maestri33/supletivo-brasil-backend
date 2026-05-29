"""Storage local da midia das materias (video/foto) em MEDIA_DIR.

Conteudo de curso (nao sensivel como documento de identidade). Salvo em
MEDIA_DIR/<material_id>/<kind><ext> e servido via endpoint GET (FileResponse),
nunca via StaticFiles aberto — controle de acesso (alerta do documents.md).
"""

import mimetypes
from pathlib import Path

from app.config import get_settings
from app.exceptions import NotFound, ValidationError

settings = get_settings()

# Prefixo de mime aceito por tipo de midia.
_KIND_PREFIX = {"video": "video/", "photo": "image/"}


def _media_root() -> Path:
    root = Path(settings.media_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def save(material_id: str, kind: str, content: bytes, filename: str, mime_type: str) -> str:
    """Valida e grava o binario. Retorna o caminho relativo (guardado no model)."""
    prefix = _KIND_PREFIX[kind]
    if not (mime_type or "").startswith(prefix):
        raise ValidationError(f"Tipo de arquivo invalido para {kind}: esperado {prefix}*")

    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise ValidationError(f"Arquivo excede o limite de {settings.max_upload_mb} MB")

    ext = Path(filename).suffix or mimetypes.guess_extension(mime_type) or ""
    rel_path = f"{material_id}/{kind}{ext}"
    dest = _media_root() / rel_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)
    return rel_path


def resolve(rel_path: str) -> tuple[Path, str]:
    """Retorna (caminho absoluto, media_type) de uma midia salva. 404 se sumiu."""
    abs_path = _media_root() / rel_path
    if not abs_path.is_file():
        raise NotFound("Arquivo de midia nao encontrado")
    media_type = mimetypes.guess_type(str(abs_path))[0] or "application/octet-stream"
    return abs_path, media_type
