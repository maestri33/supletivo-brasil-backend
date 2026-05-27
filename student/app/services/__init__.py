"""Camada de servicos — regras de negocio do aluno."""

from app.services import (
    diploma_service,
    document_service,
    exam_service,
    notifications,
    student_service,
)

__all__ = [
    "diploma_service",
    "document_service",
    "exam_service",
    "notifications",
    "student_service",
]
