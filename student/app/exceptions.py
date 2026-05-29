"""
Excecoes de dominio.

Levante estas excecoes na camada `services/`. O handler global em `main.py`
converte em resposta HTTP — services NAO importam HTTPException.
"""


class DomainError(Exception):
    """Base de todas as excecoes de dominio deste servico."""

    status_code: int = 400
    code: str = "domain_error"

    def __init__(self, message: str = "") -> None:
        super().__init__(message or self.__class__.__name__)
        self.message = message or self.__class__.__name__


class NotFound(DomainError):
    status_code = 404
    code = "not_found"


class Conflict(DomainError):
    status_code = 409
    code = "conflict"


class ValidationError(DomainError):
    status_code = 422
    code = "validation_error"


class Forbidden(DomainError):
    status_code = 403
    code = "forbidden"


class IntegrationError(DomainError):
    """Falha repetida em integracao HTTP — 502 ao cliente."""

    status_code = 502
    code = "integration_error"


# ── Student ───────────────────────────────────────────────────────────
class StudentNotFound(NotFound):
    code = "student_not_found"


class StudentAlreadyExists(Conflict):
    code = "student_already_exists"


class InvalidStatusTransition(ValidationError):
    code = "invalid_status_transition"


# ── Documents ─────────────────────────────────────────────────────────
class DocumentNotFound(NotFound):
    code = "student_document_not_found"


class DocumentAlreadyExists(Conflict):
    code = "student_document_already_exists"


class RequiredDocumentMissing(ValidationError):
    code = "required_document_missing"


# ── Exams ─────────────────────────────────────────────────────────────
class ExamNotFound(NotFound):
    code = "student_exam_not_found"


class ExamAlreadyScheduled(Conflict):
    code = "student_exam_already_scheduled"


class ExamAlreadyCorrected(Conflict):
    code = "student_exam_already_corrected"


# ── Diploma ───────────────────────────────────────────────────────────
class DiplomaNotFound(NotFound):
    code = "student_diploma_not_found"


class DiplomaAlreadyIssued(Conflict):
    code = "student_diploma_already_issued"


class DiplomaAlreadyPickedUp(Conflict):
    code = "student_diploma_already_picked_up"
