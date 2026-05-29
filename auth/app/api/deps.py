"""Dependencias FastAPI: sessao de banco e validacao de usuario."""

import uuid
from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session
from app.exceptions import NotFound
from app.models.user import User
from app.utils.logging import get_logger

logger = get_logger(__name__)


async def get_db() -> AsyncSession:  # type: ignore[valid-type]
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


DbSession = Annotated[AsyncSession, Depends(get_db)]


async def valid_user(external_id: uuid.UUID, db: DbSession) -> User:
    result = await db.execute(select(User).where(User.external_id == external_id))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFound("Usuario nao encontrado", code="USER_NOT_FOUND")
    return user
