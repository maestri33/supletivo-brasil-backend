"""pixkey service: valida chave PIX via DICT e persiste com external_id do usuario."""

from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from .. import config_store as cfg
from ..exceptions import PixKeyError
from ..integrations.asaas_client import AsaasClient, AsaasError
from ..models import PixKey
from .config_key import _doc_matches

VALID_KEY_TYPES = {"CPF", "CNPJ", "EMAIL", "PHONE", "EVP"}


def _client(db: Session) -> AsaasClient:
    api_key = cfg.get(db, cfg.K_ASAAS_API_KEY)
    if not api_key:
        raise PixKeyError("asaas_api_key_not_set")
    return AsaasClient(api_key)


def _basic_validate(key: str, key_type: str) -> None:
    k = key.strip()
    digits = "".join(ch for ch in k if ch.isdigit())
    if key_type == "CPF":
        if not (len(digits) == 11 and digits == k):
            raise PixKeyError("invalid_cpf_format")
    elif key_type == "CNPJ":
        if not (len(digits) == 14 and digits == k):
            raise PixKeyError("invalid_cnpj_format")
    elif key_type == "EMAIL":
        if "@" not in k or "." not in k.split("@")[-1]:
            raise PixKeyError("invalid_email_format")
    elif key_type == "PHONE":
        if not (k.startswith("+") and len(digits) >= 12):
            raise PixKeyError("invalid_phone_format_expected_+55DDDNNNNNNNNN")
    elif key_type == "EVP":
        if not (len(k) == 36 and k.count("-") == 4):
            raise PixKeyError("invalid_evp_format")
    else:
        raise PixKeyError("invalid_key_type")


def _dict_lookup(client: AsaasClient, pix_key: str) -> dict:
    tomorrow = (datetime.now(UTC) + timedelta(days=1)).date().isoformat()
    payload = {
        "value": 0.01,
        "pixAddressKey": pix_key,
        "scheduleDate": tomorrow,
        "externalReference": f"dict-{secrets.token_hex(6)}",
        "description": "consulta DICT (cancelada)",
    }
    try:
        created = client.create_transfer(payload)
    except AsaasError as e:
        raise PixKeyError(f"dict_lookup_failed: {e.body}") from e
    transfer_id = created.get("id")
    if transfer_id:
        try:
            client.cancel_transfer(transfer_id)
        except AsaasError:
            pass
    return created


def create(
    db: Session,
    external_id: str,
    document: str,
    key: str,
    key_type: str,
) -> PixKey:
    external_id = external_id.strip()
    key = key.strip()
    key_type = key_type.strip().upper()
    document = "".join(ch for ch in document if ch.isdigit())

    if not external_id:
        raise PixKeyError("external_id_required")
    if key_type not in VALID_KEY_TYPES:
        raise PixKeyError("invalid_key_type")
    if len(document) not in (11, 14):
        raise PixKeyError("invalid_document_length")

    _basic_validate(key, key_type)

    # dedup: external_id nao pode existir; pix key tb nao
    if db.query(PixKey).filter(PixKey.external_id == external_id).first():
        raise PixKeyError("external_id_already_exists")
    if db.query(PixKey).filter(PixKey.key == key).first():
        raise PixKeyError("pix_key_already_registered")

    client = _client(db)
    try:
        raw = _dict_lookup(client, key)
    finally:
        client.close()

    bank_account = raw.get("bankAccount") or {}
    got_doc = (bank_account.get("cpfCnpj") or "").strip()
    if not _doc_matches(got_doc, document):
        raise PixKeyError(f"holder_mismatch: expected {document} got {got_doc}")

    bank_info = bank_account.get("bank") or {}
    row = PixKey(
        external_id=external_id,
        key=key,
        key_type=key_type,
        holder_document=got_doc,
        holder_name=bank_account.get("ownerName") or bank_account.get("accountName"),
        bank_name=bank_info.get("name"),
        raw_dict=json.dumps(raw, ensure_ascii=False),
        validated_at=datetime.now(UTC),
    )
    db.add(row)
    db.flush()
    return row


def get_by_external_id(db: Session, external_id: str) -> PixKey | None:
    return db.query(PixKey).filter(PixKey.external_id == external_id).one_or_none()


def list_all(db: Session, limit: int = 200, offset: int = 0) -> list[PixKey]:
    limit = max(1, min(int(limit), 500))
    offset = max(0, int(offset))
    return db.query(PixKey).order_by(PixKey.id.desc()).offset(offset).limit(limit).all()


def get_by_key(db: Session, key: str) -> PixKey | None:
    return db.query(PixKey).filter(PixKey.key == key.strip()).one_or_none()


def check(db: Session, key: str) -> dict:
    """DB first; se nao existe, DICT lookup (nao persiste).

    Retorna {source: "db"|"dict", data: {...}}.
    """
    key = key.strip()
    row = get_by_key(db, key)
    if row is not None:
        return {"source": "db", "data": to_dict(row)}
    client = _client(db)
    try:
        raw = _dict_lookup(client, key)
    finally:
        client.close()
    bank_account = raw.get("bankAccount") or {}
    bank_info = bank_account.get("bank") or {}
    return {
        "source": "dict",
        "data": {
            "key": key,
            "holder_document": (bank_account.get("cpfCnpj") or "").strip() or None,
            "holder_name": bank_account.get("ownerName") or bank_account.get("accountName"),
            "bank_name": bank_info.get("name"),
        },
    }


def delete(db: Session, external_id: str) -> bool:
    row = get_by_external_id(db, external_id)
    if row is None:
        return False
    db.delete(row)
    db.flush()
    return True


def to_dict(row: PixKey) -> dict:
    return {
        "external_id": row.external_id,
        "key": row.key,
        "key_type": row.key_type,
        "holder_document": row.holder_document,
        "holder_name": row.holder_name,
        "bank_name": row.bank_name,
        "validated_at": row.validated_at.isoformat() if row.validated_at else None,
    }
