"""Schemas Pydantic para a API de documentos."""

from datetime import date, datetime

from pydantic import BaseModel


ALLOWED_MIME_IMG = {"image/jpeg", "image/png", "image/webp"}
IMAGE_SLOTS = frozenset(
    {
        "rg_front_photo",
        "rg_back_photo",
        "cnh_front_photo",
        "cnh_back_photo",
        "work_card_front_photo",
        "work_card_back_photo",
        "passport_front_photo",
        "passport_back_photo",
        "certificate_photo",
        "military_photo",
        "proof_of_residence_photo",
        "photo",
    }
)


# --- sub-documentos ---


class RGUpdate(BaseModel):
    number: str | None = None
    issuing_agency: str | None = None
    issue_date: date | None = None


class RGOut(BaseModel):
    id: str  # UUID
    number: str | None = None
    issuing_agency: str | None = None
    issue_date: date | None = None
    front_photo: str | None = None
    back_photo: str | None = None

    model_config = {"from_attributes": True}


class CNHUpdate(BaseModel):
    number: str | None = None
    category: str | None = None
    date_of_birth: date | None = None
    expires_on: date | None = None
    national_register: str | None = None


class CNHOut(BaseModel):
    id: str  # UUID
    number: str | None = None
    category: str | None = None
    date_of_birth: date | None = None
    expires_on: date | None = None
    national_register: str | None = None
    front_photo: str | None = None
    back_photo: str | None = None

    model_config = {"from_attributes": True}


class WorkCardUpdate(BaseModel):
    number: str | None = None
    series: str | None = None
    state: str | None = None
    issue_date: date | None = None


class WorkCardOut(BaseModel):
    id: str  # UUID
    number: str | None = None
    series: str | None = None
    state: str | None = None
    issue_date: date | None = None
    front_photo: str | None = None
    back_photo: str | None = None

    model_config = {"from_attributes": True}


class PassportUpdate(BaseModel):
    number: str | None = None
    expires_on: date | None = None
    issue_date: date | None = None


class PassportOut(BaseModel):
    id: str  # UUID
    number: str | None = None
    expires_on: date | None = None
    issue_date: date | None = None
    front_photo: str | None = None
    back_photo: str | None = None

    model_config = {"from_attributes": True}


class CertificateUpdate(BaseModel):
    kind: str | None = None
    number: str | None = None
    registry_office: str | None = None
    book: str | None = None
    page: str | None = None
    entry: str | None = None
    issue_date: date | None = None


# --- documento principal ---


class DocumentUpdate(BaseModel):
    rg: RGUpdate | None = None
    cnh: CNHUpdate | None = None
    work_card: WorkCardUpdate | None = None
    passport: PassportUpdate | None = None
    certificate: CertificateUpdate | None = None
    military_number: str | None = None
    military_series: str | None = None
    military_category: str | None = None
    military_ra: str | None = None


class DocumentOut(BaseModel):
    id: str  # UUID
    external_id: str  # UUID
    created_at: datetime
    updated_at: datetime

    rg: RGOut | None = None
    cnh: CNHOut | None = None
    work_card: WorkCardOut | None = None
    passport: PassportOut | None = None

    certificate_kind: str | None = None
    certificate_number: str | None = None
    certificate_registry_office: str | None = None
    certificate_book: str | None = None
    certificate_page: str | None = None
    certificate_entry: str | None = None
    certificate_issue_date: date | None = None
    certificate_photo: str | None = None

    military_number: str | None = None
    military_series: str | None = None
    military_category: str | None = None
    military_ra: str | None = None
    military_photo: str | None = None

    proof_of_residence_photo: str | None = None
    photo: str | None = None

    model_config = {"from_attributes": True}
