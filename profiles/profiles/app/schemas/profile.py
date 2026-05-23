"""Schemas Pydantic para CRUD de Profile — catálogo de campos e contratos de validação."""

from datetime import date
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.validators.birth_date import normalize_birth_date, validate_birth_date
from app.validators.cpf import validate_cpf
from app.validators.description import validate_description
from app.validators.educational import (
    normalize_boolean,
    validate_elementary_year,
    validate_last_elementary_year,
    validate_last_high_school_year,
    validate_level,
)
from app.validators.location import validate_city, validate_state
from app.validators.name import validate_name
from app.validators.profile_fields import (
    validate_blood_type,
    validate_civil_status,
    validate_gender,
)


# ── Educational ──────────────────────────────────────────────────

class EducationalRead(BaseModel):
    """Escolaridade no retorno da API."""

    level: Optional[str] = None
    last_elementary_year: Optional[str] = None
    elementary_completed: Optional[bool] = None
    elementary_year: Optional[int] = None
    last_high_school_year: Optional[str] = None
    high_school_completed: Optional[bool] = None

    model_config = {"from_attributes": True}


# ── BirthInfo ────────────────────────────────────────────────────

class BirthInfoRead(BaseModel):
    """Dados de nascimento no retorno da API."""

    state: Optional[str] = None
    city: Optional[str] = None
    birth_date: Optional[date] = None

    model_config = {"from_attributes": True}


# ── Profile ──────────────────────────────────────────────────────

class ProfileCreate(BaseModel):
    """Criação de perfil mínimo — apenas external_id e cpf são obrigatórios."""

    external_id: UUID = Field(description="Identificador do sistema externo (UUID), imutável")
    cpf: str = Field(
        description="CPF brasileiro, 11 dígitos, dígitos verificadores validados",
        max_length=11,
    )

    model_config = {"extra": "forbid"}

    @field_validator("cpf")
    @classmethod
    def _validar_cpf(cls, v: str) -> str:
        return validate_cpf(v)


class ProfilePatch(BaseModel):
    """PATCH parcial de Profile + Educational + BirthInfo.

    Apenas campos enviados são atualizados (exclude_unset).
    Envie null para limpar um campo.
    """

    # Profile
    name: Optional[str] = Field(default=None, description="Nome completo")
    gender: Optional[str] = Field(default=None, description='Gênero: "M" ou "F"')
    mother_name: Optional[str] = Field(default=None, description="Nome da mãe")
    father_name: Optional[str] = Field(default=None, description="Nome do pai")
    blood_type: Optional[str] = Field(default=None, description="Tipo sanguíneo (A+, B-, etc.)")
    civil_status: Optional[str] = Field(default=None, description="Estado civil")
    description: Optional[str] = Field(default=None, description="Descrição / observações")

    # Educational
    level: Optional[str] = Field(default=None, description="Nível educacional")
    last_elementary_year: Optional[str] = Field(default=None, description="Última série do fundamental")
    elementary_completed: Optional[bool] = Field(default=None, description="Fundamental completo?")
    elementary_year: Optional[int] = Field(default=None, description="Ano de conclusão do fundamental")
    last_high_school_year: Optional[str] = Field(default=None, description="Último ano do ensino médio")
    high_school_completed: Optional[bool] = Field(default=None, description="Ensino médio completo?")

    # BirthInfo
    state: Optional[str] = Field(default=None, description="UF (2 letras)")
    city: Optional[str] = Field(default=None, description="Cidade de nascimento")
    birth_date: Optional[date] = Field(default=None, description="Data de nascimento (ISO 8601)")

    model_config = {"extra": "forbid"}

    # ── Validators Profile ──────────────────────────────────────

    @field_validator("name", mode="before")
    @classmethod
    def _validar_name(cls, v):
        return validate_name(v)

    @field_validator("gender", mode="before")
    @classmethod
    def _validar_gender(cls, v):
        return validate_gender(v)

    @field_validator("mother_name", mode="before")
    @classmethod
    def _validar_mother_name(cls, v):
        return validate_name(v)

    @field_validator("father_name", mode="before")
    @classmethod
    def _validar_father_name(cls, v):
        return validate_name(v)

    @field_validator("blood_type", mode="before")
    @classmethod
    def _validar_blood_type(cls, v):
        return validate_blood_type(v)

    @field_validator("civil_status", mode="before")
    @classmethod
    def _validar_civil_status(cls, v):
        return validate_civil_status(v)

    @field_validator("description", mode="before")
    @classmethod
    def _validar_description(cls, v):
        if v is None:
            return None
        return validate_description(str(v))

    # ── Validators Educational ──────────────────────────────────

    @field_validator("level", mode="before")
    @classmethod
    def _validar_level(cls, v):
        return validate_level(v)

    @field_validator("last_elementary_year", mode="before")
    @classmethod
    def _validar_last_elementary_year(cls, v):
        return validate_last_elementary_year(v)

    @field_validator("elementary_completed", mode="before")
    @classmethod
    def _validar_elementary_completed(cls, v):
        if v is None:
            return None
        if isinstance(v, bool):
            return v
        return normalize_boolean(str(v))

    @field_validator("elementary_year", mode="before")
    @classmethod
    def _validar_elementary_year(cls, v):
        if v is None:
            return None
        if isinstance(v, int):
            year = v
            from datetime import date
            current = date.today().year
            if year < 1900 or year > current:
                from app.exceptions import ValidationError
                raise ValidationError(f"Ano do fundamental deve estar entre 1900 e {current}")
            return year
        return validate_elementary_year(str(v))

    @field_validator("last_high_school_year", mode="before")
    @classmethod
    def _validar_last_high_school_year(cls, v):
        return validate_last_high_school_year(v)

    @field_validator("high_school_completed", mode="before")
    @classmethod
    def _validar_high_school_completed(cls, v):
        if v is None:
            return None
        if isinstance(v, bool):
            return v
        return normalize_boolean(str(v))

    # ── Validators BirthInfo ────────────────────────────────────

    @field_validator("state", mode="before")
    @classmethod
    def _validar_state(cls, v):
        return validate_state(v)

    @field_validator("city", mode="before")
    @classmethod
    def _validar_city(cls, v):
        return validate_city(v)

    @field_validator("birth_date", mode="before")
    @classmethod
    def _validar_birth_date(cls, v):
        if v is None:
            return None
        if isinstance(v, date):
            return validate_birth_date(v)
        parsed = normalize_birth_date(str(v))
        return validate_birth_date(parsed) if parsed is not None else None


class ProfileRead(BaseModel):
    """Retorno completo de perfil com educational e birth_info."""

    external_id: UUID
    cpf: str
    name: Optional[str] = None
    gender: Optional[str] = None
    mother_name: Optional[str] = None
    father_name: Optional[str] = None
    blood_type: Optional[str] = None
    civil_status: Optional[str] = None
    description: Optional[str] = None
    created_at: str
    updated_at: str
    educational: Optional[EducationalRead] = None
    birth_info: Optional[BirthInfoRead] = None

    model_config = {"from_attributes": True}


class ProfileListItem(BaseModel):
    """Item resumido na listagem de perfis."""

    external_id: UUID
    cpf: str
    name: Optional[str] = None

    model_config = {"from_attributes": True}


class FirstNameResponse(BaseModel):
    """Resposta do endpoint de primeiro nome."""

    first_name: Optional[str] = Field(default=None, description="Primeiro nome")
    full_name: Optional[str] = Field(default=None, description="Nome completo")


class CPFCheckResponse(BaseModel):
    """Resposta da consulta por CPF."""

    external_id: Optional[UUID] = None
    found: bool = Field(description="True se o CPF está cadastrado")
    valid: bool = Field(description="True se os dígitos verificadores do CPF são válidos")


# ── Helper compartilhado entre services ─────────────────────────

def build_profile_read(profile, educational=None, birth_info=None) -> ProfileRead:
    """Constrói ProfileRead a partir dos modelos ORM."""
    return ProfileRead(
        external_id=profile.external_id,
        cpf=profile.cpf,
        name=profile.name,
        gender=profile.gender,
        mother_name=profile.mother_name,
        father_name=profile.father_name,
        blood_type=profile.blood_type,
        civil_status=profile.civil_status,
        description=profile.description,
        created_at=profile.created_at.isoformat() if profile.created_at else "",
        updated_at=profile.updated_at.isoformat() if profile.updated_at else "",
        educational=EducationalRead.model_validate(educational) if educational else None,
        birth_info=BirthInfoRead.model_validate(birth_info) if birth_info else None,
    )
