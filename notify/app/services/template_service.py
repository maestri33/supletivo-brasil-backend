"""Servico de templates de email — DB-backed, multi-slug.

Templates ficam em `notify.templates` (uma linha por slug). O servico
permite multiplas variantes por contexto (welcome, checkout, receipt, ...)
e mantem retrocompatibilidade pelo slug `default`.

O `default` e' criado pela migration 0002. Bootstrap opcional copia o HTML
de `data/email_template.html` se existir (para preservar customizacoes
feitas antes da migracao para DB).
"""

from pathlib import Path

import anyio
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session_maker
from app.exceptions import Conflict, DomainError, NotFound
from app.models.template import DEFAULT_SLUG, Template
from app.utils.logging import get_logger

log = get_logger(__name__)

LEGACY_TEMPLATE_FILE = Path("data/email_template.html")


# ── Operacoes basicas de DB ────────────────────────────────────────────────


async def get_by_slug(session: AsyncSession, slug: str) -> Template | None:
    return await session.scalar(select(Template).where(Template.slug == slug))


async def get_active_or_default(session: AsyncSession, slug: str | None) -> Template:
    """Retorna o template ativo pelo slug; cai no `default` se nao encontrar.

    Levanta NotFound apenas se `default` tambem nao existir (estado invalido —
    migration 0002 sempre cria o `default`).
    """
    resolved_slug = slug or DEFAULT_SLUG
    template = await session.scalar(
        select(Template).where(
            Template.slug == resolved_slug,
            Template.is_active.is_(True),
        )
    )
    if template is None and resolved_slug != DEFAULT_SLUG:
        log.warning("template.fallback_to_default", requested_slug=resolved_slug)
        template = await session.scalar(
            select(Template).where(
                Template.slug == DEFAULT_SLUG,
                Template.is_active.is_(True),
            )
        )
    if template is None:
        raise NotFound(f"Template '{resolved_slug}' nao encontrado e sem fallback default")
    return template


async def list_templates(
    session: AsyncSession,
    only_active: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> list[Template]:
    stmt = select(Template)
    if only_active:
        stmt = stmt.where(Template.is_active.is_(True))
    result = await session.scalars(stmt.order_by(Template.slug).offset(offset).limit(limit))
    return list(result.all())


async def create_template(
    session: AsyncSession,
    slug: str,
    name: str,
    html: str,
) -> Template:
    existing = await session.scalar(select(Template).where(Template.slug == slug))
    if existing:
        raise Conflict(f"Template com slug '{slug}' ja existe")

    template = Template(slug=slug, name=name, html=html, version=1, is_active=True)
    session.add(template)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise Conflict(f"Template com slug '{slug}' ja existe") from exc
    await session.refresh(template)
    log.info("template.created", slug=slug, name=name)
    return template


async def update_template(
    session: AsyncSession,
    slug: str,
    *,
    html: str | None = None,
    name: str | None = None,
    is_active: bool | None = None,
) -> Template:
    template = await get_by_slug(session, slug)
    if template is None:
        raise NotFound(f"Template '{slug}' nao encontrado")

    if html is not None and html != template.html:
        template.html = html
        template.version += 1
    if name is not None:
        template.name = name
    if is_active is not None:
        template.is_active = is_active

    await session.commit()
    await session.refresh(template)
    log.info(
        "template.updated",
        slug=slug,
        version=template.version,
        is_active=template.is_active,
    )
    return template


async def delete_template(session: AsyncSession, slug: str) -> None:
    if slug == DEFAULT_SLUG:
        raise DomainError(
            "Template 'default' nao pode ser deletado (use is_active=false para desativar)"
        )
    template = await get_by_slug(session, slug)
    if template is None:
        raise NotFound(f"Template '{slug}' nao encontrado")
    await session.delete(template)
    await session.commit()
    log.info("template.deleted", slug=slug)


# ── Edicao via IA ──────────────────────────────────────────────────────────


async def edit_with_ai(
    session: AsyncSession,
    slug: str,
    instruction: str,
) -> Template:
    """Edita o HTML de um template via servico AI e persiste."""
    import httpx

    from app.integrations.ai import AIClient

    template = await get_by_slug(session, slug)
    if template is None:
        raise NotFound(f"Template '{slug}' nao encontrado")

    system_prompt = (
        "Voce edita templates HTML de email conforme instrucoes do usuario. "
        "Retorne um JSON com a chave 'html' contendo o HTML completo editado. "
        "Preserve placeholders Jinja2 {{variavel}} intactos. "
        "Use CSS inline. O HTML deve ser responsivo e compativel com clientes de email. "
        "Textos do template sempre em portugues brasileiro com acentuacao correta."
    )
    async with httpx.AsyncClient() as client:
        ai = AIClient(client)
        result = await ai.json(
            prompt=f"Instrucao: {instruction}\n\nHTML atual:\n{template.html}",
            instruction=system_prompt,
        )
    new_html = result.get("html", template.html)
    log.info("template.ai_edited", slug=slug, instruction_preview=instruction[:80])
    return await update_template(session, slug, html=new_html)


async def create_from_default_with_ai(
    session: AsyncSession,
    slug: str,
    name: str,
    instruction: str,
) -> Template:
    """Cria um novo template a partir do `default` editado via servico AI."""
    import httpx

    from app.integrations.ai import AIClient

    default = await get_by_slug(session, DEFAULT_SLUG)
    if default is None:
        raise NotFound("Template 'default' nao existe — rode a migration 0002")

    system_prompt = (
        "Voce edita templates HTML de email conforme instrucoes do usuario. "
        "Retorne um JSON com a chave 'html' contendo o HTML completo editado. "
        "Preserve placeholders Jinja2 {{variavel}} intactos. "
        "Use CSS inline. O HTML deve ser responsivo e compativel com clientes de email. "
        "Textos do template sempre em portugues brasileiro com acentuacao correta."
    )
    async with httpx.AsyncClient() as client:
        ai = AIClient(client)
        result = await ai.json(
            prompt=f"Instrucao: {instruction}\n\nHTML atual:\n{default.html}",
            instruction=system_prompt,
        )
    new_html = result.get("html", default.html)
    log.info("template.ai_created_from_default", slug=slug, instruction_preview=instruction[:80])
    return await create_template(session, slug=slug, name=name, html=new_html)


# ── Bootstrap (chamado no lifespan) ────────────────────────────────────────


async def bootstrap_from_disk_if_needed() -> None:
    """Se `default` ainda tem o HTML literal da migration mas existe um
    `data/email_template.html` customizado em disco, migra para o DB.

    Heuristica: so importa do disco se o `default` esta na versao 1 e o
    arquivo em disco difere do que esta no DB. Idempotente — pode rodar
    em todo startup sem efeito colateral apos a primeira migracao.
    """
    if not LEGACY_TEMPLATE_FILE.exists():
        return

    async with async_session_maker() as session:
        template = await get_by_slug(session, DEFAULT_SLUG)
        if template is None or template.version != 1:
            return

        def _read() -> str:
            return LEGACY_TEMPLATE_FILE.read_text(encoding="utf-8")

        disk_html = await anyio.to_thread.run_sync(_read)
        if disk_html.strip() and disk_html != template.html:
            template.html = disk_html
            template.version += 1
            await session.commit()
            log.info(
                "template.bootstrap_from_disk",
                slug=DEFAULT_SLUG,
                path=str(LEGACY_TEMPLATE_FILE),
            )


# ── Helpers legados (compat com chamadores) ────────────────────────────────


async def get_template(slug: str | None = None) -> str:
    """Retorna o HTML do template (default se slug=None).

    Mantido para retrocompatibilidade com chamadores que nao tem session.
    Abre sua propria session.
    """
    async with async_session_maker() as session:
        template = await get_active_or_default(session, slug)
        return template.html


async def count_templates() -> dict[str, int]:
    """Contagem de templates (total / ativos)."""
    async with async_session_maker() as session:
        total = await session.scalar(select(func.count()).select_from(Template)) or 0
        active = (
            await session.scalar(
                select(func.count()).select_from(Template).where(Template.is_active.is_(True))
            )
            or 0
        )
    return {"total": int(total), "active": int(active)}
