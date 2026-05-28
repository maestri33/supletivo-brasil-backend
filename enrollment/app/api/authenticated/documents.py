"""Etapa documents — RG obrigatório; avança address → documents."""

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import upstream_errors
from app.db import get_session
from app.dependencies import require_address
from app.models import EnrollmentStatus
from app.schemas.documents import (
    RG_IMAGE_SLOTS,
    DocumentsGetResponse,
    DocumentsResponse,
    RgDataRequest,
)
from app.services import documents as documents_svc
from app.services import notifications

router = APIRouter(prefix="/api/v1/authenticated", tags=["authenticated"])


@router.get("/documents", response_model=DocumentsGetResponse, summary="Estado dos documentos")
async def get_documents(external_id=require_address()):
    with upstream_errors():
        data = await documents_svc.get_documents(str(external_id))
    return DocumentsGetResponse(**data)


@router.put("/documents/rg", response_model=DocumentsResponse, summary="Salva dados do RG")
async def put_rg(payload: RgDataRequest, external_id=require_address()):
    with upstream_errors():
        await documents_svc.save_rg_data(str(external_id), payload)
    return DocumentsResponse(status=EnrollmentStatus.ADDRESS.value, message="Dados do RG salvos")


@router.post(
    "/documents/images/{slot}",
    response_model=DocumentsResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload de imagem do RG (frente ou verso)",
)
async def upload_rg_image(
    slot: str,
    file: UploadFile = File(...),
    external_id=require_address(),
):
    if slot not in RG_IMAGE_SLOTS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"slot inválido: {slot}",
        )
    content = await file.read()
    with upstream_errors():
        await documents_svc.upload_rg_image(
            str(external_id),
            slot,
            content,
            file.filename or "upload",
            file.content_type or "application/octet-stream",
        )
    return DocumentsResponse(status=EnrollmentStatus.ADDRESS.value, message="Imagem enviada")


@router.post(
    "/documents/submit",
    response_model=DocumentsResponse,
    summary="Conclui etapa de documentos",
)
async def submit_documents(
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    external_id=require_address(),
):
    with upstream_errors():
        new_status = await documents_svc.submit_documents(session, str(external_id))
    await session.commit()
    background_tasks.add_task(notifications.notify_status_advanced, str(external_id), new_status)
    return DocumentsResponse(
        status=new_status,
        message="RG completo, informe seus dados educacionais",
    )
