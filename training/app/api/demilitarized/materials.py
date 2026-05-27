"""Rotas desmilitarizadas de autoria de materia (uso interno, sem auth — §5).

Criar/listar/buscar/atualizar materia e upload/download de video e foto.
A midia fica armazenada no proprio training (MEDIA_DIR), servida via FileResponse.
"""

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.exceptions import NotFound
from app.schemas.material import (
    MaterialCreate,
    MaterialListResponse,
    MaterialOut,
    MaterialUpdate,
)
from app.services import material as material_svc
from app.services import media as media_svc

router = APIRouter(prefix="/api/v1/demilitarized", tags=["demilitarized"])


@router.post(
    "/materials",
    response_model=MaterialOut,
    status_code=status.HTTP_201_CREATED,
    summary="Cria materia",
)
async def create_material(payload: MaterialCreate, session: AsyncSession = Depends(get_session)):
    material = await material_svc.create(
        session,
        title=payload.title,
        text_content=payload.text_content,
        question=payload.question,
        expected_answer=payload.expected_answer,
    )
    await session.commit()
    return MaterialOut.from_model(material)


@router.get("/materials", response_model=MaterialListResponse, summary="Lista materias")
async def list_materials(
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    rows = await material_svc.list_materials(session, limit=limit, offset=offset)
    return MaterialListResponse(
        total=len(rows), materials=[MaterialOut.from_model(r) for r in rows]
    )


@router.get("/materials/{material_id}", response_model=MaterialOut, summary="Busca materia")
async def get_material(material_id: str, session: AsyncSession = Depends(get_session)):
    material = await material_svc.get_or_404(session, material_id)
    return MaterialOut.from_model(material)


@router.put("/materials/{material_id}", response_model=MaterialOut, summary="Atualiza materia")
async def update_material(
    material_id: str, payload: MaterialUpdate, session: AsyncSession = Depends(get_session)
):
    material = await material_svc.update(
        session, material_id, payload.model_dump(exclude_unset=True)
    )
    await session.commit()
    return MaterialOut.from_model(material)


async def _upload(
    kind: str, material_id: str, file: UploadFile, session: AsyncSession
) -> MaterialOut:
    material = await material_svc.get_or_404(session, material_id)
    content = await file.read()
    rel_path = media_svc.save(
        material_id, kind, content, file.filename or kind, file.content_type or ""
    )
    material_svc.set_media_path(material, kind, rel_path)
    await session.commit()
    return MaterialOut.from_model(material)


@router.post(
    "/materials/{material_id}/video", response_model=MaterialOut, summary="Envia video da materia"
)
async def upload_video(
    material_id: str,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
):
    return await _upload("video", material_id, file, session)


@router.post(
    "/materials/{material_id}/photo", response_model=MaterialOut, summary="Envia foto da materia"
)
async def upload_photo(
    material_id: str,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
):
    return await _upload("photo", material_id, file, session)


async def _download(kind: str, material_id: str, session: AsyncSession) -> FileResponse:
    material = await material_svc.get_or_404(session, material_id)
    rel_path = material.video_path if kind == "video" else material.photo_path
    if not rel_path:
        raise NotFound(f"Materia sem {kind}")
    abs_path, media_type = media_svc.resolve(rel_path)
    return FileResponse(abs_path, media_type=media_type)


@router.get("/materials/{material_id}/video", summary="Baixa video da materia")
async def download_video(material_id: str, session: AsyncSession = Depends(get_session)):
    return await _download("video", material_id, session)


@router.get("/materials/{material_id}/photo", summary="Baixa foto da materia")
async def download_photo(material_id: str, session: AsyncSession = Depends(get_session)):
    return await _download("photo", material_id, session)
