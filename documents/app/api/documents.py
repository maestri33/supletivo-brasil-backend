from uuid import UUID

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse

from app.services.document_service import (
    get_or_create,
    update_document,
    upload_image,
    get_image_info,
    delete_image,
)
from app.schemas.document import DocumentOut, DocumentUpdate
from app.exceptions import (
    DocumentNotFoundError,
    InvalidSlotError,
    InvalidFileTypeError,
    FileTooLargeError,
)

router = APIRouter(prefix="/api/v1/documentos", tags=["documentos"])


@router.get("/{external_id}", response_model=DocumentOut)
async def obter(external_id: UUID):
    doc = await get_or_create(str(external_id))
    return DocumentOut.model_validate(doc)


@router.put("/{external_id}", response_model=DocumentOut)
async def atualizar(external_id: UUID, body: DocumentUpdate):
    try:
        doc = await update_document(str(external_id), body)
        return DocumentOut.model_validate(doc)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post(
    "/{external_id}/imagens/{slot}", response_model=DocumentOut, status_code=201
)
async def upload_imagem(external_id: UUID, slot: str, file: UploadFile = File(...)):
    try:
        content = await file.read()
        doc = await upload_image(
            external_id=str(external_id),
            slot=slot,
            content=content,
            original_name=file.filename or "unknown",
            mime_type=file.content_type or "application/octet-stream",
        )
        return DocumentOut.model_validate(doc)
    except InvalidSlotError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except InvalidFileTypeError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except FileTooLargeError as e:
        raise HTTPException(status_code=413, detail=str(e))


@router.get("/{external_id}/imagens/{slot}")
async def download_imagem(external_id: UUID, slot: str):
    try:
        full_path = await get_image_info(str(external_id), slot)
        return FileResponse(path=str(full_path))
    except (DocumentNotFoundError, InvalidSlotError) as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{external_id}/imagens/{slot}", response_model=DocumentOut)
async def deletar_imagem(external_id: UUID, slot: str):
    try:
        doc = await delete_image(str(external_id), slot)
        return DocumentOut.model_validate(doc)
    except InvalidSlotError as e:
        raise HTTPException(status_code=422, detail=str(e))
