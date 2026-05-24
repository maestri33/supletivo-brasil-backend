"""Camada HTTP fina e isolada sobre a API de checkout da InfinitePay.

Regras (§12):
 - INFINITEPAY_BASE_URL vem de Settings (.env).
 - Sem regra de negocio aqui. Cada funcao mapeia 1:1 um endpoint InfinitePay.
 - Levanta InfinitePayError em qualquer 2xx-com-erro ou nao-2xx (o caller decide).
 - I/O async (httpx.AsyncClient): nao bloqueia o event loop do uvicorn nem o worker.
"""

from __future__ import annotations

import httpx

from app.config import get_settings


class InfinitePayError(Exception):
    def __init__(self, message: str, payload: dict | None = None, status_code: int | None = None):
        super().__init__(message)
        self.payload = payload
        self.status_code = status_code


def _client() -> httpx.AsyncClient:
    s = get_settings()
    return httpx.AsyncClient(base_url=s.infinitepay_base_url, timeout=s.http_timeout)


async def create_checkout_link(payload: dict) -> dict:
    async with _client() as c:
        r = await c.post("/links", json=payload)
        try:
            data = r.json()
        except ValueError:
            data = {"raw": r.text}

        if r.status_code >= 400:
            raise InfinitePayError(
                f"HTTP {r.status_code} from InfinitePay", payload=data, status_code=r.status_code
            )
        if data.get("success") is False:
            raise InfinitePayError(
                "InfinitePay returned success=false", payload=data, status_code=r.status_code
            )
        if not (data.get("url") or data.get("checkout_url")):
            raise InfinitePayError(
                "InfinitePay response missing checkout URL", payload=data, status_code=r.status_code
            )
        return data


async def payment_check(*, handle: str, order_nsu: str, transaction_nsu: str, slug: str) -> dict:
    async with _client() as c:
        r = await c.post(
            "/payment_check",
            json={
                "handle": handle,
                "order_nsu": order_nsu,
                "transaction_nsu": transaction_nsu,
                "slug": slug,
            },
        )
        if r.status_code >= 400:
            try:
                data = r.json()
            except ValueError:
                data = {"raw": r.text}
            raise InfinitePayError(
                f"HTTP {r.status_code} from InfinitePay payment_check",
                payload=data,
                status_code=r.status_code,
            )
        try:
            return r.json()
        except ValueError:
            return {"success": False, "raw": r.text, "status_code": r.status_code}
