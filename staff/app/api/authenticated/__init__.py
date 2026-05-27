"""Routers autenticados (JWT + role admin/staff)."""

from fastapi import APIRouter

from app.api.authenticated.me import router as me_router

authenticated_router = APIRouter()
authenticated_router.include_router(me_router)

__all__ = ["authenticated_router"]
