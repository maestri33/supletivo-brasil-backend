"""Student document schemas."""

from datetime import datetime

from app.schemas import APIModel


class StudentDocumentCreate(APIModel):
    """Schema para criar um documento de aluno."""

    student_external_id: str
    coordinator_external_id: str
    document_type: str
    description: str
    file_path: str | None = None


class StudentDocumentResponse(APIModel):
    """Schema de resposta com dados completos do documento."""

    id: str
    student_external_id: str
    coordinator_external_id: str
    document_type: str
    description: str
    file_path: str | None = None
    submitted_to_institution: bool = False
    submitted_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class StudentDocumentListResponse(APIModel):
    """Schema para listagem paginada de documentos."""

    items: list[StudentDocumentResponse]
    total: int
