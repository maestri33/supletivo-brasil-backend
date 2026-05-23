"""Customer service — find-or-create de pagadores no Asaas.

Asaas /payments exige customer_id, entao mantemos um mapping local:
  asaas.customer.external_id (user-supplied) <-> asaas.customer.asaas_id (Asaas)

Fluxo find-or-create:
  1. Existe Customer local com esse external_id? -> retorna
  2. Senao: payer obrigatorio (name, cpf_cnpj)
     2a. Procura no Asaas por externalReference (recupera de orfaos)
     2b. Se nao existe no Asaas, cria via POST /v3/customers
  3. Persiste localmente e retorna
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from .. import config_store as cfg
from ..exceptions import ValidationError
from ..integrations.asaas_client import AsaasClient, AsaasError
from ..models import Customer
from ..utils.logging import log_event


@dataclass(frozen=True)
class PayerData:
    name: str
    cpf_cnpj: str
    email: str | None = None
    mobile_phone: str | None = None


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def _validate_cpf_cnpj(raw: str) -> str:
    digits = _digits(raw)
    if len(digits) not in (11, 14):
        raise ValidationError(f"invalid_cpf_cnpj: got {len(digits)} digits")
    return digits


def get(db: Session, external_id: str) -> Customer | None:
    if not external_id:
        return None
    return db.query(Customer).filter(Customer.external_id == external_id).one_or_none()


def get_by_asaas_id(db: Session, asaas_id: str) -> Customer | None:
    if not asaas_id:
        return None
    return db.query(Customer).filter(Customer.asaas_id == asaas_id).one_or_none()


def _persist(
    db: Session,
    *,
    external_id: str,
    asaas_id: str,
    name: str,
    cpf_cnpj: str,
    email: str | None,
    mobile_phone: str | None,
) -> Customer:
    row = Customer(
        external_id=external_id,
        asaas_id=asaas_id,
        name=name,
        cpf_cnpj=cpf_cnpj,
        email=email,
        mobile_phone=mobile_phone,
    )
    db.add(row)
    db.flush()
    return row


def _create_in_asaas(api_key: str, *, external_id: str, payer: PayerData) -> dict:
    cpf_cnpj = _validate_cpf_cnpj(payer.cpf_cnpj)
    client = AsaasClient(api_key)
    try:
        existing = client.find_customer_by_external_reference(external_id)
        if existing:
            log_event(
                "customer_found_in_asaas", external_id=external_id, asaas_id=existing.get("id")
            )
            return existing
        try:
            created = client.create_customer(
                {
                    "name": payer.name,
                    "cpfCnpj": cpf_cnpj,
                    "email": payer.email,
                    "mobilePhone": payer.mobile_phone,
                    "externalReference": external_id,
                    "notificationDisabled": True,
                }
            )
        except AsaasError as e:
            raise ValidationError(f"asaas_customer_create_failed: {e.body}") from e
        log_event("customer_created_in_asaas", external_id=external_id, asaas_id=created.get("id"))
        return created
    finally:
        client.close()


def find_or_create(
    db: Session,
    external_id: str,
    payer: PayerData | None,
) -> Customer:
    """Resolve customer por external_id; cria se nao existe (exige payer)."""
    if not external_id or not external_id.strip():
        raise ValidationError("external_id_required")
    existing = get(db, external_id)
    if existing is not None:
        return existing
    if payer is None:
        raise ValidationError("customer_required")
    api_key = cfg.get(db, cfg.K_ASAAS_API_KEY)
    if not api_key:
        raise ValidationError("asaas_api_key_not_set")
    asaas_customer = _create_in_asaas(api_key, external_id=external_id, payer=payer)
    return _persist(
        db,
        external_id=external_id,
        asaas_id=asaas_customer["id"],
        name=asaas_customer.get("name") or payer.name,
        cpf_cnpj=asaas_customer.get("cpfCnpj") or _digits(payer.cpf_cnpj),
        email=asaas_customer.get("email") or payer.email,
        mobile_phone=asaas_customer.get("mobilePhone") or payer.mobile_phone,
    )


def list_all(db: Session, limit: int = 200, offset: int = 0) -> list[Customer]:
    limit = max(1, min(int(limit), 500))
    offset = max(0, int(offset))
    return db.query(Customer).order_by(Customer.id.desc()).offset(offset).limit(limit).all()


def to_dict(row: Customer) -> dict:
    return {
        "external_id": row.external_id,
        "asaas_id": row.asaas_id,
        "name": row.name,
        "cpf_cnpj": row.cpf_cnpj,
        "email": row.email,
        "mobile_phone": row.mobile_phone,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
