"""Endpoints somente-leitura de regras de role (regras vêm do `.env`, §8 CONVENTION.md)."""

import uuid

from fastapi import APIRouter

from app.schemas.role_rule import RoleRuleRead
from app.services.role_service import get_rule_by_id, list_rules

router = APIRouter(prefix="/config/roles", tags=["config"])


@router.get("", response_model=list[RoleRuleRead])
async def list_role_rules():
    return [r.as_dict() for r in list_rules()]


@router.get("/{rule_id}", response_model=RoleRuleRead)
async def get_role_rule(rule_id: uuid.UUID):
    return get_rule_by_id(rule_id).as_dict()
