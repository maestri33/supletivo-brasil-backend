"""Endpoints de gerenciamento de email (Mailcow API).

Fornece:
  - Health/status do servidor de email
  - Listagem de dominios e mailboxes
  - Gerenciamento de aliases
  - Status da fila Postfix
  - Informacoes DKIM

Todas as operacoes de leitura sao acessiveis na camada "demilitarized".
Operacoes destrutivas (create/delete) requerem confirmacao explicita.
"""

import httpx
from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.integrations.mailcow import MailcowClient

router = APIRouter(prefix="/email", tags=["email"])


def _mailcow() -> MailcowClient:
    """Cria um MailcowClient com httpx client dedicado."""
    settings = get_settings()
    if not settings.mailcow_api_url or not settings.mailcow_api_key:
        raise HTTPException(
            status_code=503,
            detail="Mailcow API nao configurada (MAILCOW_API_URL / MAILCOW_API_KEY)",
        )
    client = httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0))
    return MailcowClient(client)


# ── Health / Status ────────────────────────────────────────────────────


@router.get("/health", summary="Health do servidor de email (Mailcow)")
async def email_health() -> dict:
    """Verifica conectividade com a API Mailcow."""
    mc = _mailcow()
    try:
        return await mc.health()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Mailcow indisponivel: {exc}") from exc


@router.get("/status", summary="Status agregado do email")
async def email_status() -> dict:
    """Dominios, mailboxes, fila — status completo do servidor de email."""
    mc = _mailcow()
    try:
        return await mc.status()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Mailcow erro: {exc}") from exc


# ── Dominios ───────────────────────────────────────────────────────────


@router.get("/domains", summary="Lista todos os dominios")
async def list_domains() -> list[dict]:
    mc = _mailcow()
    try:
        return await mc.list_domains()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/domains/{domain}", summary="Detalhes de um dominio")
async def get_domain(domain: str) -> dict:
    mc = _mailcow()
    try:
        return await mc.get_domain(domain)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


# ── Mailboxes ──────────────────────────────────────────────────────────


@router.get("/mailboxes/{domain}", summary="Lista mailboxes de um dominio")
async def list_mailboxes(domain: str) -> list[dict]:
    mc = _mailcow()
    try:
        return await mc.list_mailboxes(domain)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/mailbox/{addr:path}", summary="Detalhes de uma mailbox")
async def get_mailbox(addr: str) -> dict:
    mc = _mailcow()
    try:
        return await mc.get_mailbox(addr)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


# ── Aliases ────────────────────────────────────────────────────────────


@router.get("/aliases", summary="Lista todos os aliases")
async def list_aliases() -> list[dict]:
    mc = _mailcow()
    try:
        return await mc.list_aliases()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


# ── DKIM ───────────────────────────────────────────────────────────────


@router.get("/dkim/{domain}", summary="Chaves DKIM de um dominio")
async def get_dkim(domain: str) -> dict:
    mc = _mailcow()
    try:
        return await mc.get_dkim(domain)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


# ── Fila Postfix ───────────────────────────────────────────────────────


@router.get("/queue", summary="Status da fila Postfix")
async def get_queue() -> dict:
    mc = _mailcow()
    try:
        result = await mc.get_queue()
        return {"queue": result}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/queue/flush", summary="Forca envio da fila Postfix")
async def flush_queue() -> dict:
    mc = _mailcow()
    try:
        return await mc.flush_queue()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
