"""Etapa documents — RG ou CNH (dados + frente/verso); avanca para pixkey."""

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import upstream_errors
from app.db import get_session
from app.dependencies import require_documents
from app.models import CandidateStatus
from app.schemas.documents import (
    DOC_IMAGE_SLOTS,
    DocumentDataRequest,
    DocumentsGetResponse,
    DocumentsResponse,
)
from app.services import documents as documents_svc
from app.services import notifications

router = APIRouter(prefix="/api/v1/authenticated", tags=["authenticated"])


@router.get("/documents", response_model=DocumentsGetResponse, summary="Estado dos documentos")
async def get_documents(external_id=require_documents()):
    with upstream_errors():
        data = await documents_svc.get_documents(str(external_id))
    return DocumentsGetResponse(**data)


@router.put("/documents", response_model=DocumentsResponse, summary="Salva dados de RG ou CNH")
async def put_documents(payload: DocumentDataRequest, external_id=require_documents()):
    with upstream_errors():
        await documents_svc.save_data(str(external_id), payload)
    return DocumentsResponse(status=CandidateStatus.DOCUMENTS.value, message="Dados salvos")


@router.post(
    "/documents/images/{slot}",
    response_model=DocumentsResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload de imagem (rg/cnh frente/verso)",
)
async def upload_document_image(
    slot: str,
    file: UploadFile = File(...),
    external_id=require_documents(),
):
    if slot not in DOC_IMAGE_SLOTS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"slot invalido: {slot}",
        )
    content = await file.read()
    with upstream_errors():
        await documents_svc.upload_image(
            str(external_id),
            slot,
            content,
            file.filename or "upload",
            file.content_type or "application/octet-stream",
        )
    return DocumentsResponse(status=CandidateStatus.DOCUMENTS.value, message="Imagem enviada")


@router.post("/documents/submit", response_model=DocumentsResponse, summary="Conclui documentos")
async def submit_documents(
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    external_id=require_documents(),
):
    with upstream_errors():
        new_status = await documents_svc.submit(session, str(external_id))
    await session.commit()
    background_tasks.add_task(notifications.notify_status_advanced, str(external_id), new_status)
    return DocumentsResponse(
        status=new_status, message="Documentos concluidos, cadastre sua chave PIX"
    )
