"""Schemas Pydantic do servico student."""

from app.schemas.diplomas import DiplomaPickupRequest, StudentDiplomaRead
from app.schemas.documents import (
    DocumentSubmitRequest,
    StudentDocumentList,
    StudentDocumentRead,
)
from app.schemas.exams import (
    ExamGradeRequest,
    ExamScheduleRequest,
    StudentExamList,
    StudentExamRead,
)
from app.schemas.pending import PendingItemsResponse
from app.schemas.student import PromoteRequest, StudentRead

__all__ = [
    "DiplomaPickupRequest",
    "DocumentSubmitRequest",
    "ExamGradeRequest",
    "ExamScheduleRequest",
    "PendingItemsResponse",
    "PromoteRequest",
    "StudentDiplomaRead",
    "StudentDocumentList",
    "StudentDocumentRead",
    "StudentExamList",
    "StudentExamRead",
    "StudentRead",
]
