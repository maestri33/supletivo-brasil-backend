"""Schemas Pydantic do Address."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.validators.address_fields import validate_country, validate_kind, validate_state
from app.validators.zipcode import validate_zipcode


def _validate_required_text(value: str | None, field: str, max_len: int) -> str:
    if value is None or not str(value).strip():
        from app.exceptions import ValidationError

        raise ValidationError(f"{field} é obrigatório")
    clean = str(value).strip()
    if len(clean) > max_len:
        from app.exceptions import ValidationError

        raise ValidationError(f"{field} deve ter no máximo {max_len} caracteres")
    return clean


def _validate_optional_text(value: str | None, field: str, max_len: int) -> str | None:
    if value is None:
        return None
    clean = str(value).strip()
    if not clean:
        return None
    if len(clean) > max_len:
        from app.exceptions import ValidationError

        raise ValidationError(f"{field} deve ter no máximo {max_len} caracteres")
    return clean


class AddressCreate(BaseModel):
    """Criação de endereço. Todos os campos NOT NULL são obrigatórios."""

    external_id: UUID = Field(description="UUID do usuário em auth.users")
    kind: str = Field(description="home | billing | shipping")
    zipcode: str = Field(description="CEP — 8 dígitos, com ou sem hífen", max_length=14)
    street: str = Field(description="Logradouro", max_length=200)
    number: Optional[str] = Field(default=None, max_length=20)
    complement: Optional[str] = Field(default=None, max_length=100)
    neighborhood: Optional[str] = Field(default=None, max_length=100)
    city: str = Field(description="Cidade", max_length=100)
    state: str = Field(description="UF (2 letras)", max_length=2)
    country: Optional[str] = Field(default="BR", description="ISO-3166-1 alpha-2", max_length=2)
    lat: Optional[str] = Field(default=None, max_length=30)
    lng: Optional[str] = Field(default=None, max_length=30)

    model_config = {"extra": "forbid"}

    @field_validator("kind", mode="before")
    @classmethod
    def _v_kind(cls, v):
        return validate_kind(v)

    @field_validator("zipcode", mode="before")
    @classmethod
    def _v_zipcode(cls, v):
        return validate_zipcode(v)

    @field_validator("street", mode="before")
    @classmethod
    def _v_street(cls, v):
        return _validate_required_text(v, "street", 200)

    @field_validator("number", mode="before")
    @classmethod
    def _v_number(cls, v):
        return _validate_optional_text(v, "number", 20)

    @field_validator("complement", mode="before")
    @classmethod
    def _v_complement(cls, v):
        return _validate_optional_text(v, "complement", 100)

    @field_validator("neighborhood", mode="before")
    @classmethod
    def _v_neighborhood(cls, v):
        return _validate_optional_text(v, "neighborhood", 100)

    @field_validator("city", mode="before")
    @classmethod
    def _v_city(cls, v):
        return _validate_required_text(v, "city", 100)

    @field_validator("state", mode="before")
    @classmethod
    def _v_state(cls, v):
        return validate_state(v)

    @field_validator("country", mode="before")
    @classmethod
    def _v_country(cls, v):
        return validate_country(v)

    @field_validator("lat", mode="before")
    @classmethod
    def _v_lat(cls, v):
        return _validate_optional_text(v, "lat", 30)

    @field_validator("lng", mode="before")
    @classmethod
    def _v_lng(cls, v):
        return _validate_optional_text(v, "lng", 30)


class AddressPatch(BaseModel):
    """PATCH parcial — qualquer campo opcional."""

    kind: Optional[str] = None
    zipcode: Optional[str] = Field(default=None, max_length=14)
    street: Optional[str] = Field(default=None, max_length=200)
    number: Optional[str] = Field(default=None, max_length=20)
    complement: Optional[str] = Field(default=None, max_length=100)
    neighborhood: Optional[str] = Field(default=None, max_length=100)
    city: Optional[str] = Field(default=None, max_length=100)
    state: Optional[str] = Field(default=None, max_length=2)
    country: Optional[str] = Field(default=None, max_length=2)
    lat: Optional[str] = Field(default=None, max_length=30)
    lng: Optional[str] = Field(default=None, max_length=30)

    model_config = {"extra": "forbid"}

    @field_validator("kind", mode="before")
    @classmethod
    def _v_kind(cls, v):
        if v is None:
            return None
        return validate_kind(v)

    @field_validator("zipcode", mode="before")
    @classmethod
    def _v_zipcode(cls, v):
        if v is None:
            return None
        return validate_zipcode(v)

    @field_validator("street", mode="before")
    @classmethod
    def _v_street(cls, v):
        if v is None:
            return None
        return _validate_required_text(v, "street", 200)

    @field_validator("number", mode="before")
    @classmethod
    def _v_number(cls, v):
        return _validate_optional_text(v, "number", 20)

    @field_validator("complement", mode="before")
    @classmethod
    def _v_complement(cls, v):
        return _validate_optional_text(v, "complement", 100)

    @field_validator("neighborhood", mode="before")
    @classmethod
    def _v_neighborhood(cls, v):
        return _validate_optional_text(v, "neighborhood", 100)

    @field_validator("city", mode="before")
    @classmethod
    def _v_city(cls, v):
        if v is None:
            return None
        return _validate_required_text(v, "city", 100)

    @field_validator("state", mode="before")
    @classmethod
    def _v_state(cls, v):
        if v is None:
            return None
        return validate_state(v)

    @field_validator("country", mode="before")
    @classmethod
    def _v_country(cls, v):
        if v is None:
            return None
        return validate_country(v)

    @field_validator("lat", mode="before")
    @classmethod
    def _v_lat(cls, v):
        return _validate_optional_text(v, "lat", 30)

    @field_validator("lng", mode="before")
    @classmethod
    def _v_lng(cls, v):
        return _validate_optional_text(v, "lng", 30)


class AddressRead(BaseModel):
    id: UUID
    external_id: UUID
    kind: str
    zipcode: str
    street: str
    number: Optional[str] = None
    complement: Optional[str] = None
    neighborhood: Optional[str] = None
    city: str
    state: str
    country: str
    lat: Optional[str] = None
    lng: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ViaCepResult(BaseModel):
    """Resposta do lookup ViaCEP em GET /api/v1/addresses/cep/{zipcode}."""

    zipcode: str
    street: Optional[str] = None
    complement: Optional[str] = None
    neighborhood: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
