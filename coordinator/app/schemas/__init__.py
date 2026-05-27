"""Schemas Pydantic para o servico Coordinator.

CONVENTION §2 exige Pydantic 2.8+.
"""

from pydantic import BaseModel, ConfigDict

# ---------------------------------------------------------------------------
# APIModel — base compartilhado para todos os schemas de negócio
# ---------------------------------------------------------------------------


class APIModel(BaseModel):
    """Modelo base Pydantic para schemas de negócio do Coordinator.

    Comportamentos herdados:
    - ``extra='ignore'``  —  campos não declarados são silenciosamente ignorados.
    - ``str_strip_whitespace=True``  —  strings têm espaços extra removidos.
    - ``from_attributes=True``  —  permite conversão de ORM para Pydantic.
    """

    model_config: ConfigDict = ConfigDict(
        extra="ignore",
        str_strip_whitespace=True,
        from_attributes=True,
    )


# ---------------------------------------------------------------------------
# Coordinator
# ---------------------------------------------------------------------------
from .coordinator import (  # noqa: F401, E402
    CoordinatorCreate,
    CoordinatorResponse,
    CoordinatorUpdate,
)

# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------
from .training import (  # noqa: F401, E402
    TrainingApprovalCreate,
    TrainingApprovalListResponse,
    TrainingApprovalResponse,
    TrainingApprovalUpdate,
)

# ---------------------------------------------------------------------------
# Student Document
# ---------------------------------------------------------------------------
from .document import (  # noqa: F401, E402
    StudentDocumentCreate,
    StudentDocumentListResponse,
    StudentDocumentResponse,
)

# ---------------------------------------------------------------------------
# Enrollment
# ---------------------------------------------------------------------------
from .fee import (  # noqa: F401, E402
    EnrollmentFeeCreate,
    EnrollmentFeeListResponse,
    EnrollmentFeeResponse,
    EnrollmentFeePayRequest,
)

# ---------------------------------------------------------------------------
# Exam
# ---------------------------------------------------------------------------
from .exam import (  # noqa: F401, E402
    ExamCreate,
    ExamGradeRequest,
    ExamListResponse,
    ExamResponse,
    ExamSubmitRequest,
)

# ---------------------------------------------------------------------------
# Diploma
# ---------------------------------------------------------------------------
from .diploma import (  # noqa: F401, E402
    DiplomaCreate,
    DiplomaGraduateRequest,
    DiplomaListResponse,
    DiplomaResponse,
)

__all__ = [
    # base
    "APIModel",
    # coordinator
    "CoordinatorCreate",
    "CoordinatorResponse",
    "CoordinatorUpdate",
    # training
    "TrainingApprovalCreate",
    "TrainingApprovalResponse",
    "TrainingApprovalUpdate",
    "TrainingApprovalListResponse",
    # student document
    "StudentDocumentCreate",
    "StudentDocumentResponse",
    "StudentDocumentListResponse",
    # enrollment
    "EnrollmentFeeCreate",
    "EnrollmentFeeResponse",
    "EnrollmentFeeListResponse",
    "EnrollmentFeePayRequest",
    # exam
    "ExamCreate",
    "ExamResponse",
    "ExamSubmitRequest",
    "ExamGradeRequest",
    "ExamListResponse",
    # diploma
    "DiplomaCreate",
    "DiplomaResponse",
    "DiplomaGraduateRequest",
    "DiplomaListResponse",
]
