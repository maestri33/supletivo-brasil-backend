"""Serviço de Roles — motor de regras de transição (SQLAlchemy 2)."""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select

from app.api.router import router
from app.config import settings
from app.db import async_session_maker, engine, get_session
from app.exceptions import DomainError, NotFound, ValidationError
from app.models.role_rule import RoleRule
from app.models.user_role import UserRole

logger = logging.getLogger("roles")
started_at = datetime.now(timezone.utc)


SEEDS = [
    {"from_role": None, "to_role": "lead", "mode": "add"},
    {"from_role": "lead", "to_role": "enrollment", "mode": "replace"},
    {"from_role": "enrollment", "to_role": "student", "mode": "replace"},
    {"from_role": None, "to_role": "veteran", "mode": "add", "requires_role": "student"},
    {"from_role": None, "to_role": "candidate", "mode": "add"},
    {"from_role": "candidate", "to_role": "promoter", "mode": "replace"},
    {"from_role": None, "to_role": "coordinator", "mode": "add", "requires_role": "promoter"},
]


async def _seed_if_empty() -> None:
    async with async_session_maker() as session:
        existing = await session.scalar(select(func.count(RoleRule.id)))
        if existing and existing > 0:
            logger.info(f"Seed skipped — {existing} rules existentes")
            return
        for s in SEEDS:
            session.add(RoleRule(**s))
        await session.commit()
        logger.info(f"Seed: {len(SEEDS)} regras criadas")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _seed_if_empty()
    logger.info(f"Roles service started on port {settings.PORT}")
    yield
    await engine.dispose()


app = FastAPI(
    title="Roles Service",
    description="Motor de regras de transição de roles para o pipeline v7m.",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

app.include_router(router)


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError):
    status_map = {NotFound: 404, ValidationError: 422}
    http_status = 400
    for cls, http_code in status_map.items():
        if isinstance(exc, cls):
            http_status = http_code
            break
    return JSONResponse(
        status_code=http_status, content={"detail": exc.message, "code": exc.code},
    )


@app.get("/")
async def root():
    async with async_session_maker() as session:
        total_rules = await session.scalar(select(func.count(RoleRule.id)))
        add_rules = await session.scalar(
            select(func.count(RoleRule.id)).where(RoleRule.mode == "add")
        )
        replace_rules = await session.scalar(
            select(func.count(RoleRule.id)).where(RoleRule.mode == "replace")
        )
        blocking_rules = await session.scalar(
            select(func.count(RoleRule.id)).where(RoleRule.blocking.is_(True))
        )

        active = await session.scalars(
            select(UserRole).where(UserRole.revoked_at.is_(None))
        )
        active_list = list(active.all())

    total_assignments = len(active_list)
    users_with_roles = len({r.external_id for r in active_list})

    role_distribution: dict[str, int] = {}
    for r in active_list:
        role_distribution[r.role] = role_distribution.get(r.role, 0) + 1

    top_roles = dict(
        sorted(role_distribution.items(), key=lambda x: x[1], reverse=True)[:10]
    )

    uptime = str(datetime.now(timezone.utc) - started_at).split(".")[0]

    return {
        "service": settings.SERVICE_NAME,
        "version": app.version,
        "uptime": uptime,
        "rules": {
            "total": total_rules,
            "add": add_rules,
            "replace": replace_rules,
            "blocking": blocking_rules,
        },
        "users": {
            "total_with_roles": users_with_roles,
            "total_active_assignments": total_assignments,
        },
        "roles": top_roles,
    }


@app.get("/health")
async def health():
    return {"status": "ok", "service": settings.SERVICE_NAME}


@app.get("/ready")
async def ready():
    return {"status": "ok", "service": settings.SERVICE_NAME}


@app.get("/status")
async def status():
    return {
        "status": "ok",
        "service": settings.SERVICE_NAME,
        "version": app.version,
        "uptime_seconds": int((datetime.now(timezone.utc) - started_at).total_seconds()),
    }


if __name__ == "__main__":
    uvicorn.run(app, host=settings.HOST, port=settings.PORT)
