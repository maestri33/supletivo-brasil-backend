"""Endpoint de limpeza atomica do ecossistema — two-step para evitar acidentes."""

from __future__ import annotations

import uuid

import niquests
from fastapi import APIRouter, Request

from app.config import get_settings

router = APIRouter(prefix="/atomic", tags=["atomic"])

ATOMIC_KEY = "atomic:wipe"
ATOMIC_TTL = 60  # 1 minuto para confirmar

settings = get_settings()

SERVICES = [
    ("auth", "postgresql", None),
    ("profiles", f"{settings.PROFILES_SERVICE_URL}/api/v1/profiles", None),
    ("roles", f"{settings.ROLES_SERVICE_URL}/api/v1/role", None),
    ("notify", f"{settings.NOTIFY_SERVICE_URL}/api/v1/contacts", None),
    ("lead", f"{settings.LEAD_SERVICE_URL}/api/v1/demilitarized", None),
]


@router.post("", status_code=201, summary="Gera token de limpeza atomica (valido por 60s)")
async def atomic_create(request: Request) -> dict:
    """Cria um token unico para confirmacao da limpeza total."""
    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        return {"detail": "Redis indisponivel", "code": "REDIS_DOWN"}

    token = str(uuid.uuid4())
    await redis.setex(ATOMIC_KEY, ATOMIC_TTL, token)
    return {
        "atomic_id": token,
        "ttl": ATOMIC_TTL,
        "message": f"DELETE /api/v1/atomic/{token} para confirmar",
    }


@router.delete("/{atomic_id}", summary="Executa limpeza total do ecossistema")
async def atomic_execute(atomic_id: str, request: Request) -> dict:
    """Confirma o token e apaga todos os dados de todos os servicos."""
    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        return {"detail": "Redis indisponivel", "code": "REDIS_DOWN"}

    stored = await redis.get(ATOMIC_KEY)
    if stored is None:
        return {
            "detail": "Nenhum token ativo. Crie um com POST /atomic primeiro.",
            "code": "NO_TOKEN",
        }
    if stored != atomic_id:
        return {"detail": "Token invalido.", "code": "BAD_TOKEN"}

    # Token valido — remove imediatamente para evitar reentrada
    await redis.delete(ATOMIC_KEY)

    results: dict[str, dict] = {}

    # 1. Auth DB
    try:
        from app.db import engine
        from app.models.user import Base

        async with engine.begin() as conn:
            for table in reversed(Base.metadata.sorted_tables):
                await conn.execute(table.delete())
        results["auth"] = {"status": "ok", "deleted": "all"}
    except Exception as exc:
        results["auth"] = {"status": "error", "detail": str(exc)}

    # 2. Profiles — deleta perfis conhecidos
    try:
        async with niquests.AsyncSession() as s:
            # GET all profiles primeiro
            resp = await s.get(
                f"{settings.PROFILES_SERVICE_URL}/api/v1/profiles",
                timeout=10,
            )
            if resp.status_code == 200:
                profiles = resp.json()
                deleted = 0
                for p in profiles:
                    eid = p.get("external_id")
                    if eid:
                        dr = await s.delete(
                            f"{settings.PROFILES_SERVICE_URL}/api/v1/profiles/{eid}",
                            timeout=5,
                        )
                        if dr.status_code == 204:
                            deleted += 1
                results["profiles"] = {"status": "ok", "deleted": deleted}
            else:
                results["profiles"] = {
                    "status": "no_list_endpoint",
                    "detail": f"HTTP {resp.status_code}",
                }
    except Exception as exc:
        results["profiles"] = {"status": "error", "detail": str(exc)}

    # 3. Roles — deleta usuarios (nao as regras)
    try:
        async with niquests.AsyncSession() as s:
            resp = await s.get(
                f"{settings.ROLES_SERVICE_URL}/api/v1/users",
                timeout=10,
            )
            if resp.status_code == 200:
                users = resp.json()
                deleted = 0
                for u in users:
                    eid = u.get("external_id") if isinstance(u, dict) else u
                    if eid:
                        dr = await s.delete(
                            f"{settings.ROLES_SERVICE_URL}/api/v1/users/{eid}",
                            timeout=5,
                        )
                        if dr.status_code in (200, 204):
                            deleted += 1
                results["roles"] = {"status": "ok", "deleted": deleted}
            else:
                results["roles"] = {"status": "error", "detail": f"HTTP {resp.status_code}"}
    except Exception as exc:
        results["roles"] = {"status": "error", "detail": str(exc)}

    # 4. Notify — deleta contatos
    try:
        async with niquests.AsyncSession() as s:
            resp = await s.get(
                f"{settings.NOTIFY_SERVICE_URL}/api/v1/contacts",
                timeout=10,
            )
            if resp.status_code == 200:
                contacts = resp.json()
                deleted = 0
                for c in contacts:
                    eid = c.get("external_id")
                    if eid:
                        dr = await s.delete(
                            f"{settings.NOTIFY_SERVICE_URL}/api/v1/contacts/{eid}",
                            timeout=5,
                        )
                        if dr.status_code in (200, 204):
                            deleted += 1
                results["notify"] = {"status": "ok", "deleted": deleted}
            else:
                results["notify"] = {
                    "status": "no_list_endpoint",
                    "detail": f"HTTP {resp.status_code}",
                }
    except Exception as exc:
        results["notify"] = {"status": "error", "detail": str(exc)}

    # 5. Lead — deleta leads e checkouts
    try:
        base = f"{settings.LEAD_SERVICE_URL}/api/v1/demilitarized"
        async with niquests.AsyncSession() as s:
            # Leads
            resp = await s.get(f"{base}/leads", timeout=10)
            if resp.status_code == 200:
                leads = resp.json()
                deleted_leads = 0
                for item in leads:
                    eid = item.get("external_id") if isinstance(item, dict) else item
                    if eid:
                        dr = await s.delete(f"{base}/leads/{eid}", timeout=5)
                        if dr.status_code in (200, 204):
                            deleted_leads += 1
                results["lead_leads"] = {"status": "ok", "deleted": deleted_leads}
            else:
                results["lead_leads"] = {"status": "error", "detail": f"HTTP {resp.status_code}"}

            # Checkouts
            resp = await s.get(f"{base}/checkouts", timeout=10)
            if resp.status_code == 200:
                checkouts = resp.json()
                deleted_co = 0
                for item in checkouts:
                    eid = item.get("external_id") if isinstance(item, dict) else item
                    if eid:
                        dr = await s.delete(f"{base}/checkouts/{eid}", timeout=5)
                        if dr.status_code in (200, 204):
                            deleted_co += 1
                results["lead_checkouts"] = {"status": "ok", "deleted": deleted_co}
            else:
                results["lead_checkouts"] = {
                    "status": "error",
                    "detail": f"HTTP {resp.status_code}",
                }
    except Exception as exc:
        results["lead"] = {"status": "error", "detail": str(exc)}

    # 6. OTP — expira sozinho
    results["otp"] = {"status": "skipped", "detail": "OTPs expiram automaticamente"}

    # 7. Limpa Redis logs
    try:
        await redis.delete("logs:all")
        results["redis_logs"] = {"status": "ok"}
    except Exception:
        results["redis_logs"] = {"status": "error"}

    return {"atomic_id": atomic_id, "results": results}
