"""Endpoints de gestão de roles por usuário (SQLAlchemy 2)."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.schemas.user_role import UserRolesResponse, UsersListResponse
from app.services.role_service import (
    assign_role,
    delete_user,
    get_roles,
    is_blocked,
    list_users,
    promote,
)

router = APIRouter(prefix="/role", tags=["role"])


@router.get("", response_model=UsersListResponse)
async def get_all_users(session: AsyncSession = Depends(get_session)):
    users = await list_users(session)
    return {"total": len(users), "users": users}


@router.get("/{external_id}", response_model=UserRolesResponse)
async def get_user_roles(external_id: UUID, session: AsyncSession = Depends(get_session)):
    return await get_roles(session, external_id)


@router.get("/{external_id}/blocked")
async def check_blocked(external_id: UUID, session: AsyncSession = Depends(get_session)):
    blocked = await is_blocked(session, external_id)
    return {"external_id": str(external_id), "blocked": blocked}


@router.post("/{external_id}/{role}", status_code=200)
async def assign(
    external_id: UUID, role: str, session: AsyncSession = Depends(get_session),
):
    roles = await assign_role(session, external_id, role)
    return {"external_id": str(external_id), "roles": roles}


@router.post("/{external_id}/up/{to_role}", status_code=200)
async def promote_role(
    external_id: UUID, to_role: str, session: AsyncSession = Depends(get_session),
):
    roles = await promote(session, external_id, to_role)
    return {"external_id": str(external_id), "roles": roles}


@router.delete("/{external_id}", status_code=200)
async def remove_user(external_id: UUID, session: AsyncSession = Depends(get_session)):
    count = await delete_user(session, external_id)
    return {"external_id": str(external_id), "deleted": count}
