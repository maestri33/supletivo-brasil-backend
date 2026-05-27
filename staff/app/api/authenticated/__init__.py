"""Routers autenticados (JWT + role admin/staff)."""

from fastapi import APIRouter

from app.api.authenticated.me import router as me_router
from app.api.authenticated.hubs import router as hubs_router
from app.api.authenticated.health import router as health_router

authenticated_router = APIRouter()
authenticated_router.include_router(me_router)
authenticated_router.include_router(hubs_router)
authenticated_router.include_router(health_router)

__all__ = ["authenticated_router"]
