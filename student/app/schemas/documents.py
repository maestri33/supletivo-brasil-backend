"""Schemas Pydantic v2 — documentos do aluno."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.student_document import DocumentType, ValidationStatus


class DocumentSubmitRequest(BaseModel):
    """POST /students/me/documents — aluno cadastra referencia a um documento."""

    document_type: DocumentType
    document_external_id: UUID


class StudentDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    student_id: UUID
    document_type: DocumentType
    document_external_id: UUID
    validation_status: ValidationStatus
    validation_result: dict[str, Any] | None
    validated_at: datetime | None
    created_at: datetime
    updated_at: datetime


class StudentDocumentList(BaseModel):
    items: list[StudentDocumentRead]
    total: int
