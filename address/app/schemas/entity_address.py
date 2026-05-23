"""Schemas Pydantic da EntityAddress (vínculo polimórfico)."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AddressDraftRead(BaseModel):
    """Endereço genérico/avulso da entidade — todos os campos opcionais."""

    id: int
    street: Optional[str] = None
    number: Optional[str] = None
    complement: Optional[str] = None
    neighborhood: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zipcode: Optional[str] = None
    lat: Optional[str] = None
    lng: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EntityAddressRead(BaseModel):
    id: int
    entity_type: str
    external_id: str
    proof_file: Optional[str] = None
    address: Optional[AddressDraftRead] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
