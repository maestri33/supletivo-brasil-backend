"""Lógica de negócio: atribuição e promoção de roles.

Regras de transição vêm do catálogo lido do `.env` (`services.rule_catalog`).
A tabela `roles.user_roles` guarda só quem tem qual role agora + histórico.
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFound, ValidationError
from app.models.user_role import UserRole
from app.services import rule_catalog
from app.services.rule_catalog import RuleSpec


async def _get_active(session: AsyncSession, external_id: UUID) -> list[str]:
    result = await session.scalars(
        select(UserRole.role).where(
            UserRole.external_id == external_id,
            UserRole.revoked_at.is_(None),
        )
    )
    return sorted(result.all())


async def _commit_assignment(session: AsyncSession, external_id: UUID) -> None:
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise NotFound(
            f"Usuário '{external_id}' não encontrado",
            code="USER_NOT_FOUND",
        ) from exc


def list_rules() -> list[RuleSpec]:
    return list(rule_catalog.all_rules())


def get_rule_by_id(rule_id: UUID) -> RuleSpec:
    rule = rule_catalog.get_rule_by_id(rule_id)
    if not rule:
        raise NotFound(f"Regra {rule_id} não encontrada", code="ROLE_NOT_FOUND")
    return rule


async def assign_role(session: AsyncSession, external_id: UUID, role: str) -> list[str]:
    rule = rule_catalog.find_rule(to_role=role, from_role=None)

    if not rule:
        any_rule = rule_catalog.find_any_rule(role)
        if any_rule and any_rule.mode == "replace":
            raise ValidationError(
                f"Role '{role}' não pode ser atribuída diretamente — "
                f"é uma role de promoção a partir de '{any_rule.from_role}'. "
                f"Use /role/{external_id}/up/{role}.",
                code="INVALID_ROLE_ASSIGNMENT",
            )
        if any_rule and any_rule.requires_role:
            raise ValidationError(
                f"Role '{role}' exige role '{any_rule.requires_role}' ativa.",
                code="INVALID_ROLE_ASSIGNMENT",
            )
        raise NotFound(
            f"Regra para role '{role}' não encontrada",
            code="ROLE_NOT_FOUND",
        )

    currently_active = await _get_active(session, external_id)

    if rule.requires_role and rule.requires_role not in currently_active:
        raise ValidationError(
            f"Role '{role}' exige role '{rule.requires_role}' ativa",
            code="INVALID_ROLE_ASSIGNMENT",
        )

    if rule.forbids_role and rule.forbids_role in currently_active:
        raise ValidationError(
            f"Role '{role}' é incompatível com role '{rule.forbids_role}' ativa",
            code="INVALID_ROLE_ASSIGNMENT",
        )

    if role in currently_active:
        raise ValidationError(
            f"Usuário já possui role '{role}'",
            code="INVALID_ROLE_ASSIGNMENT",
        )

    session.add(UserRole(external_id=external_id, role=role))
    await _commit_assignment(session, external_id)
    return await _get_active(session, external_id)


async def promote(session: AsyncSession, external_id: UUID, to_role: str) -> list[str]:
    rule = rule_catalog.find_promotion_rule(to_role)
    if not rule:
        raise ValidationError(
            f"Promoção para '{to_role}' não existe",
            code="INVALID_ROLE_PROMOTION",
        )
    if not rule.from_role:
        raise ValidationError(
            f"'{to_role}' não é alcançável por promoção",
            code="INVALID_ROLE_PROMOTION",
        )

    from_role = rule.from_role
    currently_active = await _get_active(session, external_id)

    if from_role not in currently_active:
        raise ValidationError(
            f"Usuário não possui role '{from_role}' ativa",
            code="INVALID_ROLE_PROMOTION",
        )

    if rule.forbids_role and rule.forbids_role in currently_active:
        raise ValidationError(
            f"Role '{to_role}' é incompatível com role '{rule.forbids_role}' ativa",
            code="INVALID_ROLE_PROMOTION",
        )

    if to_role in currently_active:
        raise ValidationError(
            f"Usuário já possui role '{to_role}'",
            code="INVALID_ROLE_PROMOTION",
        )

    current = await session.scalar(
        select(UserRole)
        .where(
            UserRole.external_id == external_id,
            UserRole.role == from_role,
            UserRole.revoked_at.is_(None),
        )
        .limit(1)
    )
    if current:
        current.revoked_at = datetime.now(timezone.utc)

    session.add(UserRole(external_id=external_id, role=to_role))
    await session.commit()
    return await _get_active(session, external_id)


async def get_roles(session: AsyncSession, external_id: UUID) -> dict:
    roles = await _get_active(session, external_id)
    return {"external_id": str(external_id), "roles": roles}


async def list_users(session: AsyncSession) -> list[dict]:
    result = await session.scalars(select(UserRole).where(UserRole.revoked_at.is_(None)))
    users: dict[str, list[str]] = {}
    for r in result.all():
        users.setdefault(str(r.external_id), []).append(r.role)
    return [{"external_id": eid, "roles": sorted(roles)} for eid, roles in sorted(users.items())]


async def delete_user(session: AsyncSession, external_id: UUID) -> int:
    result = await session.execute(delete(UserRole).where(UserRole.external_id == external_id))
    await session.commit()
    return result.rowcount or 0


async def is_blocked(session: AsyncSession, external_id: UUID) -> bool:
    active = await _get_active(session, external_id)
    if not active:
        return False
    blocking = rule_catalog.blocking_roles()
    return any(r in blocking for r in active)
