"""Helper de borda: traduz erro de servico upstream em HTTPException.

Mantem o status code e o corpo do servico chamado (ex.: 422 do auth vira 422
aqui, com o mesmo detail). Use ao redor de chamadas a services que falam HTTP.
"""

from contextlib import contextmanager
from typing import Any

import httpx
from fastapi import HTTPException


def _detail(exc: httpx.HTTPStatusError) -> Any:
    try:
        return exc.response.json()
    except Exception:  # noqa: BLE001
        return exc.response.text


@contextmanager
def upstream_errors():
    try:
        yield
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=_detail(exc)) from exc
