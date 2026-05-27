"""Schemas da etapa de documentos (RG ou CNH).

Os dados e imagens sao persistidos no servico `documents`; o candidate so
orquestra (envia dados/fotos e valida completude para avancar).
"""

from datetime import date
from typing import Literal

from pydantic import Field

from app.schemas import APIModel

# Slots de imagem aceitos nesta etapa (subconjunto do documents-service).
DOC_IMAGE_SLOTS = frozenset(
    {"rg_foto_frente", "rg_foto_verso", "cnh_foto_frente", "cnh_foto_verso"}
)


class DocumentsGetResponse(APIModel):
    message: str = "Envie seu RG ou CNH (dados + frente e verso)"
    rg_numero: str | None = None
    rg_foto_frente: bool = False
    rg_foto_verso: bool = False
    cnh_numero: str | None = None
    cnh_foto_frente: bool = False
    cnh_foto_verso: bool = False


class DocumentDataRequest(APIModel):
    doc_type: Literal["rg", "cnh"] = Field(..., description="Tipo de documento")
    numero: str = Field(..., min_length=2, max_length=30)
    # RG
    orgao_emissor: str | None = Field(None, max_length=50)
    data_emissao: date | None = None
    # CNH
    categoria: str | None = Field(None, max_length=10)
    data_nascimento: date | None = None
    validade: date | None = None
    registro_nacional: str | None = Field(None, max_length=30)


class DocumentsResponse(APIModel):
    status: str
    message: str = ""
