import httpx
from pathlib import Path

from app.config import settings
from app.models.document import Document, CERTIDAO_TIPOS
from app.models.rg import RG
from app.models.cnh import CNH
from app.models.carteira_trabalho import CarteiraTrabalho
from app.models.passaporte import Passaporte
from app.exceptions import (
    DocumentNotFoundError,
    InvalidSlotError,
    InvalidFileTypeError,
    FileTooLargeError,
)
from app.schemas.document import DocumentUpdate, ALLOWED_MIME_IMG, IMAGE_SLOTS
from app.utils.logging import get_logger

logger = get_logger(__name__)


SUB_SLOT_MAP: dict[str, tuple[str, str]] = {
    "rg_foto_frente": ("rg", "foto_frente"),
    "rg_foto_verso": ("rg", "foto_verso"),
    "cnh_foto_frente": ("cnh", "foto_frente"),
    "cnh_foto_verso": ("cnh", "foto_verso"),
    "carteira_trabalho_foto_frente": ("carteira_trabalho", "foto_frente"),
    "carteira_trabalho_foto_verso": ("carteira_trabalho", "foto_verso"),
    "passaporte_foto_frente": ("passaporte", "foto_frente"),
    "passaporte_foto_verso": ("passaporte", "foto_verso"),
}


def _doc_dir(external_id: str) -> Path:
    d = Path(settings.media_root) / "documentos" / external_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_file(external_id: str, slot: str, content: bytes, original_name: str) -> str:
    ext = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else "bin"
    filename = f"{slot}.{ext}"
    full_path = _doc_dir(external_id) / filename
    full_path.write_bytes(content)
    return f"documentos/{external_id}/{filename}"


def _delete_file(file_path: str):
    full = Path(settings.media_root) / file_path
    if full.exists():
        full.unlink()


async def _fire_webhook(event: str, payload: dict):
    if not settings.webhook_url:
        return
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(
                settings.webhook_url, json={"event": event, "payload": payload}
            )
    except Exception:
        logger.warning("webhook_falhou", webhook_event=event)


async def get_or_create(external_id: str) -> Document:
    doc = await Document.get_or_none(external_id=external_id).prefetch_related(
        "rg", "cnh", "carteira_trabalho", "passaporte"
    )
    if doc is None:
        doc = await Document.create(external_id=external_id)
        logger.info("documento_criado", external_id=external_id)
        await _fire_webhook("documento.criado", {"external_id": external_id})
        doc = await Document.get_or_none(external_id=external_id).prefetch_related(
            "rg", "cnh", "carteira_trabalho", "passaporte"
        )
    return doc


async def _get_or_create_sub(model_class, doc: Document, fk_field: str):
    sub_id = getattr(doc, f"{fk_field}_id", None)
    if sub_id is not None:
        sub = await model_class.get_or_none(id=sub_id)
        if sub is not None:
            return sub
    sub = await model_class.create()
    setattr(doc, fk_field, sub)
    await doc.save()
    return sub


async def update_document(external_id: str, data: DocumentUpdate) -> Document:
    doc = await get_or_create(external_id)
    changes = {}

    sub_updates = {
        "rg": (RG, data.rg, ["numero", "orgao_emissor", "data_emissao"]),
        "cnh": (
            CNH,
            data.cnh,
            ["numero", "categoria", "data_nascimento", "validade", "registro_nacional"],
        ),
        "carteira_trabalho": (
            CarteiraTrabalho,
            data.carteira_trabalho,
            ["numero", "serie", "uf", "data_emissao"],
        ),
        "passaporte": (
            Passaporte,
            data.passaporte,
            ["numero", "validade", "data_emissao"],
        ),
    }

    for fk_field, (model_class, update_data, fields) in sub_updates.items():
        if update_data is None:
            continue
        sub = await _get_or_create_sub(model_class, doc, fk_field)
        for field in fields:
            value = getattr(update_data, field, None)
            if value is not None:
                setattr(sub, field, value)
                changes[f"{fk_field}_{field}"] = value
        await sub.save()

    if data.certidao is not None:
        c = data.certidao
        if c.tipo is not None:
            if c.tipo not in CERTIDAO_TIPOS:
                raise ValueError(f"certidao_tipo inválido: {c.tipo}")
            doc.certidao_tipo = c.tipo
            changes["certidao_tipo"] = c.tipo
        if c.numero is not None:
            doc.certidao_numero = c.numero
            changes["certidao_numero"] = c.numero
        if c.cartorio is not None:
            doc.certidao_cartorio = c.cartorio
            changes["certidao_cartorio"] = c.cartorio
        if c.livro is not None:
            doc.certidao_livro = c.livro
            changes["certidao_livro"] = c.livro
        if c.folha is not None:
            doc.certidao_folha = c.folha
            changes["certidao_folha"] = c.folha
        if c.termo is not None:
            doc.certidao_termo = c.termo
            changes["certidao_termo"] = c.termo
        if c.data_emissao is not None:
            doc.certidao_data_emissao = c.data_emissao
            changes["certidao_data_emissao"] = c.data_emissao

    simples = {
        "reservista_numero": data.reservista_numero,
        "reservista_serie": data.reservista_serie,
        "reservista_categoria": data.reservista_categoria,
        "reservista_ra": data.reservista_ra,
    }
    for field, value in simples.items():
        if value is not None:
            setattr(doc, field, value)
            changes[field] = value

    await doc.save()
    logger.info("documento_atualizado", external_id=external_id, changes=changes)
    await _fire_webhook(
        "documento.atualizado", {"external_id": external_id, "changes": changes}
    )

    return await get_or_create(external_id)


SUBS_FOR_SLOT = {
    "rg": RG,
    "cnh": CNH,
    "carteira_trabalho": CarteiraTrabalho,
    "passaporte": Passaporte,
}


async def upload_image(
    external_id: str, slot: str, content: bytes, original_name: str, mime_type: str
) -> Document:
    if slot not in IMAGE_SLOTS:
        raise InvalidSlotError(f"slot inválido: {slot}")
    if mime_type not in ALLOWED_MIME_IMG:
        raise InvalidFileTypeError(f"tipo de arquivo não permitido: {mime_type}")
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise FileTooLargeError(f"arquivo excede limite de {settings.max_upload_mb}MB")

    doc = await get_or_create(external_id)
    relative_path = _write_file(external_id, slot, content, original_name)

    if slot in SUB_SLOT_MAP:
        sub_name, sub_field = SUB_SLOT_MAP[slot]
        model_class = SUBS_FOR_SLOT[sub_name]
        sub = await _get_or_create_sub(model_class, doc, sub_name)
        old_path = getattr(sub, sub_field, None)
        setattr(sub, sub_field, relative_path)
        await sub.save()
    else:
        old_path = getattr(doc, slot, None)
        setattr(doc, slot, relative_path)

    await doc.save(update_fields=["updated_at"])

    if old_path:
        _delete_file(old_path)

    logger.info("imagem_uploaded", external_id=external_id, slot=slot)
    await _fire_webhook(
        "documento.imagem_uploaded", {"external_id": external_id, "slot": slot}
    )

    return await get_or_create(external_id)


async def get_image_info(external_id: str, slot: str) -> Path:
    if slot not in IMAGE_SLOTS:
        raise InvalidSlotError(f"slot inválido: {slot}")
    doc = await get_or_create(external_id)

    if slot in SUB_SLOT_MAP:
        sub_name, sub_field = SUB_SLOT_MAP[slot]
        sub_id = getattr(doc, f"{sub_name}_id", None)
        if sub_id is None:
            raise DocumentNotFoundError(f"slot {slot} vazio para {external_id}")
        model_class = SUBS_FOR_SLOT[sub_name]
        sub = await model_class.get_or_none(id=sub_id)
        if sub is None:
            raise DocumentNotFoundError(f"slot {slot} vazio para {external_id}")
        path_str = getattr(sub, sub_field, None)
    else:
        path_str = getattr(doc, slot, None)

    if not path_str:
        raise DocumentNotFoundError(f"slot {slot} vazio para {external_id}")
    full_path = Path(settings.media_root) / path_str
    if not full_path.exists():
        raise DocumentNotFoundError(f"arquivo não encontrado para {external_id}/{slot}")
    return full_path


async def delete_image(external_id: str, slot: str) -> Document:
    if slot not in IMAGE_SLOTS:
        raise InvalidSlotError(f"slot inválido: {slot}")
    doc = await get_or_create(external_id)

    toupdate = False
    if slot in SUB_SLOT_MAP:
        sub_name, sub_field = SUB_SLOT_MAP[slot]
        sub_id = getattr(doc, f"{sub_name}_id", None)
        if sub_id is not None:
            model_class = SUBS_FOR_SLOT[sub_name]
            sub = await model_class.get_or_none(id=sub_id)
            if sub is not None:
                old_path = getattr(sub, sub_field, None)
                if old_path:
                    _delete_file(old_path)
                    setattr(sub, sub_field, None)
                    await sub.save()
                    toupdate = True
    else:
        old_path = getattr(doc, slot, None)
        if old_path:
            _delete_file(old_path)
            setattr(doc, slot, None)
            toupdate = True

    if toupdate:
        await doc.save(update_fields=["updated_at"])

    logger.info("imagem_deleted", external_id=external_id, slot=slot)
    await _fire_webhook(
        "documento.imagem_deleted", {"external_id": external_id, "slot": slot}
    )

    return await get_or_create(external_id)
