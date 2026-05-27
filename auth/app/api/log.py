"""Endpoint de consulta de logs."""

from fastapi import APIRouter, Depends, Query, Request

from app.api.auth_guard import require_admin
from app.schemas.log import LogEntry
from app.utils import logging as logs_tool

router = APIRouter(prefix="/log", tags=["log"])


@router.get(
    "",
    summary="Consultar logs de chamadas (API + clients externos)",
    response_model=list[LogEntry],
)
async def query_logs(
    request: Request,
    _admin: dict = Depends(require_admin),
    direction: str | None = Query(default=None, description="in | out"),
    service: str | None = Query(default=None, description="auth | notify | data"),
    method: str | None = Query(default=None, description="GET | POST | PUT | DELETE"),
    status: int | None = Query(default=None, description="HTTP status code"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict:
    results = await logs_tool.query_logs(
        getattr(request.app.state, "redis", None),
        direction=direction,  # type: ignore[arg-type]
        service=service,
        method=method,
        status=status,
        limit=limit,
        offset=offset,
    )
    return {"total": len(results), "limit": limit, "offset": offset, "logs": results}


@router.delete("", status_code=204, summary="Limpar todos os logs")
async def clear_logs(
    request: Request,
    _admin: dict = Depends(require_admin),
) -> None:
    await logs_tool.clear_logs(getattr(request.app.state, "redis", None))
