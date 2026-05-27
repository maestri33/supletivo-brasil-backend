"""Routers autenticados (JWT obrigatorio, role conferida) — §5."""

from app.api.authenticated.diplomas import router as diplomas_router
from app.api.authenticated.documents import router as documents_router
from app.api.authenticated.exams import router as exams_router
from app.api.authenticated.pending import router as pending_router
from app.api.authenticated.students import router as students_router

__all__ = [
    "diplomas_router",
    "documents_router",
    "exams_router",
    "pending_router",
    "students_router",
]
