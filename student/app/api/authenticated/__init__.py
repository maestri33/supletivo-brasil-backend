"""Routers autenticados (JWT obrigatorio, role conferida) — §5."""

from app.api.authenticated.students import router as students_router

__all__ = ["students_router"]
