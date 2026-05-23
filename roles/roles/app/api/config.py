"""Endpoints CRUD de regras de role (SQLAlchemy 2)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.schemas.role_rule import RoleRuleCreate, RoleRuleRead, RoleRuleUpdate
from app.services.role_service import (
    create_rule,
    delete_rule,
    get_rule_by_id,
    list_rules,
    update_rule,
)

router = APIRouter(prefix="/config/roles", tags=["config"])


@router.get("", response_model=list[RoleRuleRead])
async def list_role_rules(session: AsyncSession = Depends(get_session)):
    return await list_rules(session)


@router.get("/{rule_id}", response_model=RoleRuleRead)
async def get_role_rule(rule_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    return await get_rule_by_id(session, rule_id)


@router.post("", status_code=201, response_model=RoleRuleRead)
async def create_role_rule(
    data: RoleRuleCreate,
    session: AsyncSession = Depends(get_session),
):
    if data.mode not in ("add", "replace"):
        raise HTTPException(400, "mode deve ser 'add' ou 'replace'")
    return await create_rule(session, data)


@router.patch("/{rule_id}", response_model=RoleRuleRead)
async def update_role_rule(
    rule_id: uuid.UUID,
    data: RoleRuleUpdate,
    session: AsyncSession = Depends(get_session),
):
    return await update_rule(session, rule_id, data)


@router.delete("/{rule_id}", status_code=204)
async def delete_role_rule(
    rule_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    await delete_rule(session, rule_id)
