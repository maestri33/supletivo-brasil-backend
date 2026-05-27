"""Models do schema student. Importados pelo alembic via `import app.models`."""

from app.models.student import Student, StudentStatus
from app.models.student_diploma import StudentDiploma
from app.models.student_document import (
    REQUIRED_DOCUMENT_TYPES,
    DocumentType,
    StudentDocument,
    ValidationStatus,
)
from app.models.student_exam import ExamResult, StudentExam

__all__ = [
    "REQUIRED_DOCUMENT_TYPES",
    "DocumentType",
    "ExamResult",
    "Student",
    "StudentDiploma",
    "StudentDocument",
    "StudentExam",
    "StudentStatus",
    "ValidationStatus",
]
