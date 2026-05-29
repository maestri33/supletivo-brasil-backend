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

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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


async def get(db: AsyncSession, external_id: str) -> Customer | None:
    if not external_id:
        return None
    return (
        await db.execute(select(Customer).where(Customer.external_id == external_id))
    ).scalar_one_or_none()


async def get_by_asaas_id(db: AsyncSession, asaas_id: str) -> Customer | None:
    if not asaas_id:
        return None
    return (
        await db.execute(select(Customer).where(Customer.asaas_id == asaas_id))
    ).scalar_one_or_none()


async def _persist(
    db: AsyncSession,
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
    await db.flush()
    return row


async def _create_in_asaas(api_key: str, *, external_id: str, payer: PayerData) -> dict:
    cpf_cnpj = _validate_cpf_cnpj(payer.cpf_cnpj)
    async with AsaasClient(api_key) as client:
        existing = await client.find_customer_by_external_reference(external_id)
        if existing:
            log_event(
                "customer_found_in_asaas", external_id=external_id, asaas_id=existing.get("id")
            )
            return existing
        try:
            created = await client.create_customer(
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


async def find_or_create(
    db: AsyncSession,
    external_id: str,
    payer: PayerData | None,
) -> Customer:
    """Resolve customer por external_id; cria se nao existe (exige payer)."""
    if not external_id or not external_id.strip():
        raise ValidationError("external_id_required")
    existing = await get(db, external_id)
    if existing is not None:
        return existing
    if payer is None:
        raise ValidationError("customer_required")
    api_key = await cfg.get(db, cfg.K_ASAAS_API_KEY)
    if not api_key:
        raise ValidationError("asaas_api_key_not_set")
    asaas_customer = await _create_in_asaas(api_key, external_id=external_id, payer=payer)
    return await _persist(
        db,
        external_id=external_id,
        asaas_id=asaas_customer["id"],
        name=asaas_customer.get("name") or payer.name,
        cpf_cnpj=asaas_customer.get("cpfCnpj") or _digits(payer.cpf_cnpj),
        email=asaas_customer.get("email") or payer.email,
        mobile_phone=asaas_customer.get("mobilePhone") or payer.mobile_phone,
    )


async def list_all(db: AsyncSession, limit: int = 200, offset: int = 0) -> list[Customer]:
    limit = max(1, min(int(limit), 500))
    offset = max(0, int(offset))
    return list(
        (
            await db.execute(
                select(Customer)
                .order_by(Customer.created_at.desc(), Customer.id.desc())
                .offset(offset)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )


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
