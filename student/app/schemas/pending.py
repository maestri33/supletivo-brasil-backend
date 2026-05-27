"""Schemas Pydantic v2 — listagem de pendencias do aluno (PRD §5.6)."""

from pydantic import BaseModel

from app.models.student import StudentStatus
from app.schemas.documents import StudentDocumentRead


class PendingItemsResponse(BaseModel):
    """Resposta minima: status atual + documentos reprovados (decisao da sessao)."""

    status: StudentStatus
    rejected_documents: list[StudentDocumentRead]
