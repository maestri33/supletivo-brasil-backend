"""Serviço de EntityAddress — vínculo polimórfico (SQLAlchemy 2).

Feature do LOCAL portada: get-or-create, preenchimento por ViaCEP, upload de
comprovante e unlink (com preservação de histórico).
"""

import os
import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.exceptions import NotFound
from app.integrations import viacep
from app.models.entity_address import EntityAddress, EntityAddressDetail
from app.schemas.entity_address import EntityAddressRead

settings = get_settings()


async def _by_key(
    session: AsyncSession, entity_type: str, external_id: str,
) -> EntityAddress | None:
    return await session.scalar(
        select(EntityAddress).where(
            EntityAddress.entity_type == entity_type,
            EntityAddress.external_id == external_id,
        )
    )


async def _by_id(session: AsyncSession, ea_id: int) -> EntityAddress:
    return await session.scalar(select(EntityAddress).where(EntityAddress.id == ea_id))


async def get_or_create(
    session: AsyncSession, entity_type: str, external_id: str,
) -> EntityAddressRead:
    ea = await _by_key(session, entity_type, external_id)
    if ea:
        return EntityAddressRead.model_validate(ea)

    detail = EntityAddressDetail()
    ea = EntityAddress(entity_type=entity_type, external_id=external_id, address=detail)
    session.add(ea)
    await session.commit()
    return EntityAddressRead.model_validate(await _by_id(session, ea.id))


async def update_address_by_cep(
    session: AsyncSession, entity_type: str, external_id: str, cep: str,
) -> EntityAddressRead:
    ea = await _by_key(session, entity_type, external_id)
    if not ea:
        raise NotFound(f"EntityAddress {entity_type}/{external_id} não encontrado")

    if ea.address is None:
        ea.address = EntityAddressDetail()
        session.add(ea.address)

    cep_clean = re.sub(r"\D", "", cep or "")
    data = await viacep.lookup(cep_clean)

    if data:
        for key, val in data.items():
            setattr(ea.address, key, val)
    else:
        # ViaCEP fora do ar ou CEP inexistente: salva só o zipcode.
        ea.address.zipcode = cep_clean or None

    await session.commit()
    return EntityAddressRead.model_validate(await _by_id(session, ea.id))


async def upload_proof(
    session: AsyncSession, entity_type: str, external_id: str, file,
) -> EntityAddressRead:
    ea = await _by_key(session, entity_type, external_id)
    if not ea:
        raise NotFound(f"EntityAddress {entity_type}/{external_id} não encontrado")

    ext = file.filename.rsplit(".", 1)[-1] if file.filename and "." in file.filename else "bin"
    filename = f"proof_{ea.id}_{external_id}_{uuid.uuid4().hex[:8]}.{ext}"
    os.makedirs(settings.upload_dir, exist_ok=True)
    filepath = os.path.join(settings.upload_dir, filename)

    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)

    ea.proof_file = filename
    await session.commit()
    return EntityAddressRead.model_validate(await _by_id(session, ea.id))


async def unlink_and_create_new(
    session: AsyncSession, entity_type: str, external_id: str,
) -> EntityAddressRead:
    old = await _by_key(session, entity_type, external_id)
    if old:
        old.external_id = f"{external_id}_unlinked_{old.id}"
        await session.commit()

    detail = EntityAddressDetail()
    ea = EntityAddress(entity_type=entity_type, external_id=external_id, address=detail)
    session.add(ea)
    await session.commit()
    return EntityAddressRead.model_validate(await _by_id(session, ea.id))
