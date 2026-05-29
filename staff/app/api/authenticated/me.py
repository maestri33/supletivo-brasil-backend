"""Endpoint de prova do gate JWT+role — GET /api/v1/authenticated/me.

Retorna o external_id do usuario autenticado se o token for valido
e o role pertencer a STAFF_ROLES. Sem token → 403; token invalido → 401.
"""

from uuid import UUID

from fastapi import APIRouter, Depends

from app.dependencies import get_current_external_id

router = APIRouter(tags=["authenticated"])


@router.get("/me", summary="Identidade do usuario autenticado (prova do gate JWT+role)")
async def get_me(
    external_id: UUID = Depends(get_current_external_id),
) -> dict:
    return {"external_id": str(external_id)}
