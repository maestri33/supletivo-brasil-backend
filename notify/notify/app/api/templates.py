"""Endpoints de templates de email — CRUD por slug + edicao via IA."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.exceptions import DomainError
from app.schemas.template import (
    TemplateCreate,
    TemplateRead,
    TemplateSummary,
    TemplateUpdate,
)
from app.services import template_service

router = APIRouter()


@router.get("", response_model=list[TemplateSummary], summary="Listar templates")
async def list_templates(
    only_active: bool = Query(default=False, description="Filtra is_active=true"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[TemplateSummary]:
    templates = await template_service.list_templates(
        session, only_active=only_active, limit=limit, offset=offset,
    )
    return [TemplateSummary.model_validate(t, from_attributes=True) for t in templates]


@router.post(
    "",
    response_model=TemplateRead,
    status_code=status.HTTP_201_CREATED,
    summary="Criar template",
)
async def create_template(
    payload: TemplateCreate, session: AsyncSession = Depends(get_session),
) -> TemplateRead:
    if payload.html and payload.instruction:
        raise DomainError("Informe apenas html OU instruction, nao ambos")
    if not payload.html and not payload.instruction:
        raise DomainError("Informe html ou instruction")

    if payload.instruction:
        template = await template_service.create_from_default_with_ai(
            session, slug=payload.slug, name=payload.name, instruction=payload.instruction,
        )
    else:
        template = await template_service.create_template(
            session, slug=payload.slug, name=payload.name, html=payload.html or "",
        )
    return TemplateRead.model_validate(template, from_attributes=True)


@router.get("/{slug}", response_model=TemplateRead, summary="Obter template por slug")
async def get_template(
    slug: str, session: AsyncSession = Depends(get_session),
) -> TemplateRead:
    template = await template_service.get_active_or_default(session, slug)
    return TemplateRead.model_validate(template, from_attributes=True)


@router.put("/{slug}", response_model=TemplateRead, summary="Atualizar template")
async def update_template(
    slug: str,
    payload: TemplateUpdate,
    session: AsyncSession = Depends(get_session),
) -> TemplateRead:
    if payload.html and payload.instruction:
        raise DomainError("Informe apenas html OU instruction, nao ambos")

    if payload.instruction:
        template = await template_service.edit_with_ai(session, slug, payload.instruction)
        if payload.name is not None or payload.is_active is not None:
            template = await template_service.update_template(
                session, slug, name=payload.name, is_active=payload.is_active,
            )
    else:
        template = await template_service.update_template(
            session,
            slug,
            html=payload.html,
            name=payload.name,
            is_active=payload.is_active,
        )
    return TemplateRead.model_validate(template, from_attributes=True)


@router.delete(
    "/{slug}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deletar template (slug != 'default')",
)
async def delete_template(
    slug: str, session: AsyncSession = Depends(get_session),
) -> None:
    await template_service.delete_template(session, slug)


# ── Compat com clientes legados (/templates/email) ─────────────────────────


@router.get("/email/legacy", summary="[Legacy] Template default em formato antigo")
async def get_email_template_legacy(session: AsyncSession = Depends(get_session)) -> dict:
    """Mantido para clientes que ainda usam GET /templates/email/legacy.

    Retorna apenas o HTML do `default`. Preferir GET /templates/default.
    """
    template = await template_service.get_active_or_default(session, None)
    return {"html": template.html}
