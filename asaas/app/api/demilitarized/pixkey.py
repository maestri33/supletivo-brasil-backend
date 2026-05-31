"""Rotas /pixkey."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...schemas import OkResponse, PixKeyCheckResponse, PixKeyResponse, responses_for
from ...services import pixkey as svc

router = APIRouter(prefix="/pixkey", tags=["pixkey"])


class CreatePixKeyRequest(BaseModel):
    external_id: str = Field(
        ..., min_length=1, description="ID unico do destinatario no sistema cliente"
    )
    document: str = Field(
        ..., description="CPF com 11 digitos ou CNPJ com 14 digitos do titular esperado"
    )
    key: str = Field(..., min_length=3, description="Chave Pix a validar no DICT")
    key_type: str = Field(..., description="Tipo da chave: CPF, CNPJ, EMAIL, PHONE ou EVP")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "external_id": "diandra_celular",
                "document": "07461638947",
                "key": "+5542998171770",
                "key_type": "PHONE",
            }
        }
    )


@router.post(
    "",
    response_model=PixKeyResponse,
    responses=responses_for(
        "asaas_api_key_not_set",
        "external_id_required",
        "external_id_already_exists",
        "pix_key_already_registered",
        "invalid_key_type",
        "invalid_document_length",
        "invalid_cpf_format",
        "invalid_cnpj_format",
        "invalid_email_format",
        "invalid_phone_format_expected_+55DDDNNNNNNNNN",
        "invalid_evp_format",
        "holder_mismatch",
        "dict_lookup_failed",
    ),
    summary="Cadastrar e validar pixkey",
    response_description="Pixkey persistida com dados do titular retornados pelo DICT.",
)
async def create(body: CreatePixKeyRequest, db: AsyncSession = Depends(get_session)):
    """Valida a chave no DICT, compara documento esperado e salva para pagamentos futuros."""
    try:
        row = await svc.create(db, body.external_id, body.document, body.key, body.key_type)
    except svc.PixKeyError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return svc.to_dict(row)


@router.get(
    "",
    response_model=list[PixKeyResponse],
    summary="Listar pixkeys",
    response_description="Lista paginada de chaves Pix cadastradas.",
)
async def list_keys(
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_session),
):
    return [svc.to_dict(r) for r in await svc.list_all(db, limit=limit, offset=offset)]


@router.get(
    "/check/{key:path}",
    response_model=PixKeyCheckResponse,
    responses=responses_for("asaas_api_key_not_set", "dict_lookup_failed"),
    summary="Consultar pixkey sem salvar",
    response_description="Dados DICT encontrados no banco ou consultados no Asaas sem persistir.",
)
async def check_key(key: str, db: AsyncSession = Depends(get_session)):
    """Consulta DB primeiro; se a chave nao existir localmente, faz lookup DICT no Asaas."""
    try:
        return await svc.check(db, key)
    except svc.PixKeyError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get(
    "/{external_id}",
    response_model=PixKeyResponse,
    responses=responses_for(status_map={404: ["not_found"]}),
    summary="Buscar pixkey por external_id",
    response_description="Pixkey cadastrada.",
)
async def get_key(external_id: str, db: AsyncSession = Depends(get_session)):
    row = await svc.get_by_external_id(db, external_id)
    if row is None:
        raise HTTPException(status_code=404, detail="not_found")
    return svc.to_dict(row)


@router.delete(
    "/{external_id}",
    response_model=OkResponse,
    responses=responses_for(status_map={404: ["not_found"]}),
    summary="Remover pixkey",
    response_description="Confirmacao de remocao.",
)
async def delete_key(external_id: str, db: AsyncSession = Depends(get_session)):
    ok = await svc.delete(db, external_id)
    await db.commit()
    if not ok:
        raise HTTPException(status_code=404, detail="not_found")
    return {"ok": True}
