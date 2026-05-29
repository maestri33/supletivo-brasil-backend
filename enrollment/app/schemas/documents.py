"""Schemas da etapa documents — RG obrigatório (TODO: "sim obrigatório RG").

Dados e imagens persistem no serviço `documents`; enrollment orquestra e
valida completude (número + frente + verso) antes de avançar.
"""

from datetime import date

from pydantic import Field

from app.schemas import APIModel

# Slots de imagem aceitos nesta etapa — só RG (CNH não é exigido na matrícula).
RG_IMAGE_SLOTS = frozenset({"rg_foto_frente", "rg_foto_verso"})


class DocumentsGetResponse(APIModel):
    message: str = "Envie seu RG (dados + frente e verso)"
    rg_numero: str | None = None
    rg_orgao_emissor: str | None = None
    rg_data_emissao: date | None = None
    rg_foto_frente: bool = False
    rg_foto_verso: bool = False


class RgDataRequest(APIModel):
    numero: str = Field(..., min_length=2, max_length=30)
    orgao_emissor: str | None = Field(None, max_length=50)
    data_emissao: date | None = None


class DocumentsResponse(APIModel):
    status: str
    message: str = ""
