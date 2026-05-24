"""Helpers de origem da requisicao — usados na auditoria do webhook publico (§5)."""

from fastapi import Request


def client_ip(request: Request) -> str | None:
    """IP de origem do cliente.

    Atras do proxy/Docker o peer direto e o proxy; o IP real do cliente chega em
    X-Forwarded-For (primeiro item da lista) ou X-Real-IP. Fallback: peer direto.
    """
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    real = request.headers.get("x-real-ip")
    if real:
        return real.strip()
    return request.client.host if request.client else None


def user_agent(request: Request) -> str | None:
    """User-Agent bruto (origem declarada pelo chamador)."""
    return request.headers.get("user-agent")
