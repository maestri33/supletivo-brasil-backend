from pydantic import BaseModel
from datetime import date, datetime
from uuid import UUID


ALLOWED_MIME_IMG = {"image/jpeg", "image/png", "image/webp"}
IMAGE_SLOTS = frozenset(
    {
        "rg_foto_frente",
        "rg_foto_verso",
        "cnh_foto_frente",
        "cnh_foto_verso",
        "carteira_trabalho_foto_frente",
        "carteira_trabalho_foto_verso",
        "passaporte_foto_frente",
        "passaporte_foto_verso",
        "certidao_foto",
        "reservista_foto",
        "comprovante_residencia_foto",
        "foto",
    }
)


# --- sub-documentos ---


class RGUpdate(BaseModel):
    numero: str | None = None
    orgao_emissor: str | None = None
    data_emissao: date | None = None


class RGOut(BaseModel):
    id: int
    numero: str | None = None
    orgao_emissor: str | None = None
    data_emissao: date | None = None
    foto_frente: str | None = None
    foto_verso: str | None = None

    class Config:
        from_attributes = True


class CNHUpdate(BaseModel):
    numero: str | None = None
    categoria: str | None = None
    data_nascimento: date | None = None
    validade: date | None = None
    registro_nacional: str | None = None


class CNHOut(BaseModel):
    id: int
    numero: str | None = None
    categoria: str | None = None
    data_nascimento: date | None = None
    validade: date | None = None
    registro_nacional: str | None = None
    foto_frente: str | None = None
    foto_verso: str | None = None

    class Config:
        from_attributes = True


class CarteiraTrabalhoUpdate(BaseModel):
    numero: str | None = None
    serie: str | None = None
    uf: str | None = None
    data_emissao: date | None = None


class CarteiraTrabalhoOut(BaseModel):
    id: int
    numero: str | None = None
    serie: str | None = None
    uf: str | None = None
    data_emissao: date | None = None
    foto_frente: str | None = None
    foto_verso: str | None = None

    class Config:
        from_attributes = True


class PassaporteUpdate(BaseModel):
    numero: str | None = None
    validade: date | None = None
    data_emissao: date | None = None


class PassaporteOut(BaseModel):
    id: int
    numero: str | None = None
    validade: date | None = None
    data_emissao: date | None = None
    foto_frente: str | None = None
    foto_verso: str | None = None

    class Config:
        from_attributes = True


class CertidaoUpdate(BaseModel):
    tipo: str | None = None
    numero: str | None = None
    cartorio: str | None = None
    livro: str | None = None
    folha: str | None = None
    termo: str | None = None
    data_emissao: date | None = None


# --- documento principal ---


class DocumentUpdate(BaseModel):
    rg: RGUpdate | None = None
    cnh: CNHUpdate | None = None
    carteira_trabalho: CarteiraTrabalhoUpdate | None = None
    passaporte: PassaporteUpdate | None = None
    certidao: CertidaoUpdate | None = None
    reservista_numero: str | None = None
    reservista_serie: str | None = None
    reservista_categoria: str | None = None
    reservista_ra: str | None = None


class DocumentOut(BaseModel):
    id: int
    external_id: UUID
    created_at: datetime
    updated_at: datetime

    rg: RGOut | None = None
    cnh: CNHOut | None = None
    carteira_trabalho: CarteiraTrabalhoOut | None = None
    passaporte: PassaporteOut | None = None

    certidao_tipo: str | None = None
    certidao_numero: str | None = None
    certidao_cartorio: str | None = None
    certidao_livro: str | None = None
    certidao_folha: str | None = None
    certidao_termo: str | None = None
    certidao_data_emissao: date | None = None
    certidao_foto: str | None = None

    reservista_numero: str | None = None
    reservista_serie: str | None = None
    reservista_categoria: str | None = None
    reservista_ra: str | None = None
    reservista_foto: str | None = None

    comprovante_residencia_foto: str | None = None
    foto: str | None = None

    class Config:
        from_attributes = True
