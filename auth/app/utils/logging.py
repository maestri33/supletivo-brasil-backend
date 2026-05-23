"""Armazenamento e consulta de logs de chamadas (API e clients externos)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Literal

LOG_KEY = "logs:all"
MAX_LOGS = 500
Direction = Literal["in", "out"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def store_log(
    redis,
    *,
    direction: Direction,
    service: str,
    method: str,
    path: str,
    status: int,
    request_body: dict | None = None,
    response_body: dict | None = None,
    duration_ms: int = 0,
) -> None:
    """Armazena um log no Redis (LPUSH + LTRIM). No-op se Redis indisponivel."""
    if redis is None:
        return
    try:
        entry = {
            "timestamp": _now(),
            "direction": direction,
            "service": service,
            "method": method,
            "path": path,
            "status": status,
            "request_body": request_body,
            "response_body": response_body,
            "duration_ms": duration_ms,
        }
        await redis.lpush(LOG_KEY, json.dumps(entry, default=str))
        await redis.ltrim(LOG_KEY, 0, MAX_LOGS - 1)
    except Exception:
        pass


async def query_logs(
    redis,
    *,
    direction: Direction | None = None,
    service: str | None = None,
    method: str | None = None,
    status: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """Consulta logs com filtros. Retorna vazio se Redis indisponivel."""
    if redis is None:
        return []
    try:
        raw_list = await redis.lrange(LOG_KEY, 0, MAX_LOGS - 1)
    except Exception:
        return []
    results: list[dict] = []

    for raw in raw_list:
        try:
            entry = json.loads(raw)
        except json.JSONDecodeError:
            continue

        if direction is not None and entry.get("direction") != direction:
            continue
        if service is not None and entry.get("service") != service:
            continue
        if method is not None and entry.get("method") != method:
            continue
        if status is not None and entry.get("status") != status:
            continue

        results.append(entry)

    return results[offset : offset + limit]


async def clear_logs(redis) -> None:
    """Remove todos os logs. No-op se Redis indisponivel."""
    if redis is None:
        return
    try:
        await redis.delete(LOG_KEY)
    except Exception:
        pass
