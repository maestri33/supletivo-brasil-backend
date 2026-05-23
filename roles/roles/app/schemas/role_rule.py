"""Schemas para RoleRule."""

import uuid
from typing import Optional

from app.schemas import CustomModel


class RoleRuleCreate(CustomModel):
    from_role: Optional[str] = None
    to_role: str
    mode: str
    requires_role: Optional[str] = None
    forbids_role: Optional[str] = None
    blocking: bool = False


class RoleRuleUpdate(CustomModel):
    from_role: Optional[str] = None
    to_role: Optional[str] = None
    mode: Optional[str] = None
    requires_role: Optional[str] = None
    forbids_role: Optional[str] = None
    blocking: Optional[bool] = None


class RoleRuleRead(CustomModel):
    id: uuid.UUID
    from_role: Optional[str]
    to_role: str
    mode: str
    requires_role: Optional[str]
    forbids_role: Optional[str]
    blocking: bool
