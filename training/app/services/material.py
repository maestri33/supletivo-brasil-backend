"""Operacoes de banco da Material: criar, buscar, listar, atualizar."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFound
from app.models import Material


async def create(
    session: AsyncSession,
    *,
    title: str,
    text_content: str,
    question: str,
    expected_answer: str,
) -> Material:
    material = Material(
        title=title,
        text_content=text_content,
        question=question,
        expected_answer=expected_answer,
    )
    session.add(material)
    await session.flush()
    return material


async def get(session: AsyncSession, material_id: str) -> Material | None:
    return await session.scalar(select(Material).where(Material.id == str(material_id)))


async def get_or_404(session: AsyncSession, material_id: str) -> Material:
    material = await get(session, material_id)
    if material is None:
        raise NotFound("Materia nao encontrada")
    return material


async def list_materials(
    session: AsyncSession, *, limit: int = 200, offset: int = 0
) -> list[Material]:
    # desempate por id para paginacao estavel (mesma regra do candidate)
    stmt = (
        select(Material)
        .order_by(Material.created_at.desc(), Material.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(await session.scalars(stmt))


async def update(session: AsyncSession, material_id: str, fields: dict) -> Material:
    """Atualiza apenas os campos informados (None = nao mexe)."""
    material = await get_or_404(session, material_id)
    for key, value in fields.items():
        if value is not None:
            setattr(material, key, value)
    await session.flush()
    return material


def set_media_path(material: Material, kind: str, path: str) -> None:
    """Grava o caminho relativo da midia recem-salva no model (`video`/`photo`)."""
    if kind == "video":
        material.video_path = path
    else:
        material.photo_path = path
