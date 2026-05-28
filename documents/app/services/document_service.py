import httpx
from pathlib import Path

from app.config import settings
from app.models.document import Document, CERTIFICATE_KINDS
from app.models.rg import RG
from app.models.cnh import CNH
from app.models.work_card import WorkCard
from app.models.passport import Passport
from app.exceptions import (
    DocumentNotFoundError,
    InvalidSlotError,
    InvalidFileTypeError,
    FileTooLargeError,
)
from app.schemas.document import DocumentUpdate, ALLOWED_MIME_IMG, IMAGE_SLOTS
from app.utils.logging import get_logger
from app.utils.pii import mask_number

logger = get_logger(__name__)


SUB_SLOT_MAP: dict[str, tuple[str, str]] = {
    "rg_front_photo": ("rg", "front_photo"),
    "rg_back_photo": ("rg", "back_photo"),
    "cnh_front_photo": ("cnh", "front_photo"),
    "cnh_back_photo": ("cnh", "back_photo"),
    "work_card_front_photo": ("work_card", "front_photo"),
    "work_card_back_photo": ("work_card", "back_photo"),
    "passport_front_photo": ("passport", "front_photo"),
    "passport_back_photo": ("passport", "back_photo"),
}


def _doc_dir(external_id: str) -> Path:
    d = Path(settings.media_root) / "documents" / external_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_file(external_id: str, slot: str, content: bytes, original_name: str) -> str:
    ext = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else "bin"
    filename = f"{slot}.{ext}"
    full_path = _doc_dir(external_id) / filename
    full_path.write_bytes(content)
    return f"documents/{external_id}/{filename}"


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
        logger.warning("webhook_failed", webhook_event=event)


async def get_or_create(external_id: str) -> Document:
    doc = await Document.get_or_none(external_id=external_id).prefetch_related(
        "rg", "cnh", "work_card", "passport"
    )
    if doc is None:
        doc = await Document.create(external_id=external_id)
        logger.info("document_created", external_id=external_id)
        await _fire_webhook("document.created", {"external_id": external_id})
        doc = await Document.get_or_none(external_id=external_id).prefetch_related(
            "rg", "cnh", "work_card", "passport"
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
        "rg": (RG, data.rg, ["number", "issuing_agency", "issue_date"]),
        "cnh": (
            CNH,
            data.cnh,
            ["number", "category", "date_of_birth", "expires_on", "national_register"],
        ),
        "work_card": (
            WorkCard,
            data.work_card,
            ["number", "series", "state", "issue_date"],
        ),
        "passport": (
            Passport,
            data.passport,
            ["number", "expires_on", "issue_date"],
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

    if data.certificate is not None:
        c = data.certificate
        if c.kind is not None:
            if c.kind not in CERTIFICATE_KINDS:
                raise ValueError(f"certificate_kind inválido: {c.kind}")
            doc.certificate_kind = c.kind
            changes["certificate_kind"] = c.kind
        if c.number is not None:
            doc.certificate_number = c.number
            changes["certificate_number"] = c.number
        if c.registry_office is not None:
            doc.certificate_registry_office = c.registry_office
            changes["certificate_registry_office"] = c.registry_office
        if c.book is not None:
            doc.certificate_book = c.book
            changes["certificate_book"] = c.book
        if c.page is not None:
            doc.certificate_page = c.page
            changes["certificate_page"] = c.page
        if c.entry is not None:
            doc.certificate_entry = c.entry
            changes["certificate_entry"] = c.entry
        if c.issue_date is not None:
            doc.certificate_issue_date = c.issue_date
            changes["certificate_issue_date"] = c.issue_date

    simples = {
        "military_number": data.military_number,
        "military_series": data.military_series,
        "military_category": data.military_category,
        "military_ra": data.military_ra,
    }
    for field, value in simples.items():
        if value is not None:
            setattr(doc, field, value)
            changes[field] = value

    await doc.save()
    _PII_SUFFIXES = {"number", "ra", "book", "page", "entry", "registry_office"}
    masked = {
        k: mask_number(v)
        if any(suffix in k for suffix in _PII_SUFFIXES) and isinstance(v, str)
        else v
        for k, v in changes.items()
    }
    logger.info("document_updated", external_id=external_id, changes=masked)
    await _fire_webhook(
        "document.updated", {"external_id": external_id, "changes": changes}
    )

    return await get_or_create(external_id)


SUBS_FOR_SLOT = {
    "rg": RG,
    "cnh": CNH,
    "work_card": WorkCard,
    "passport": Passport,
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

    logger.info("image_uploaded", external_id=external_id, slot=slot)
    await _fire_webhook(
        "document.image_uploaded", {"external_id": external_id, "slot": slot}
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

    logger.info("image_deleted", external_id=external_id, slot=slot)
    await _fire_webhook(
        "document.image_deleted", {"external_id": external_id, "slot": slot}
    )

    return await get_or_create(external_id)
