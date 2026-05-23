"""Endpoints de listagem e remoção de usuários (SQLAlchemy 2)."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.schemas.user_role import UsersListResponse
from app.services.role_service import delete_user, list_users

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=UsersListResponse)
async def list_all_users(session: AsyncSession = Depends(get_session)):
    users = await list_users(session)
    return {"total": len(users), "users": users}


@router.delete("/{external_id}")
async def remove_user(external_id: UUID, session: AsyncSession = Depends(get_session)):
    count = await delete_user(session, external_id)
    return {"external_id": str(external_id), "deleted": count}
