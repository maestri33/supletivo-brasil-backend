"""Schemas Pydantic para o servico Coordinator (Parte B — Sprint futuro).

CONVENTION §2 exige Pydantic 2.8+.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# APIModel — base compartilhado para todos os schemas de negócio
# ---------------------------------------------------------------------------


class APIModel(BaseModel):
    """Modelo base Pydantic para schemas de negócio do Coordinator.

    Comportamentos herdados:
    - ``extra='ignore'``  —  campos não declarados são silenciosamente ignorados.
    - ``str_strip_whitespace=True``  —  strings têm espaços extra removidos.
    """

    model_config: ConfigDict = ConfigDict(
        extra="ignore",
        str_strip_whitespace=True,
    )


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------
from .training import (  # noqa: F401, E402
    TrainingApprovalRequest,
    TrainingApprovalResponse,
    TrainingStatus,
)

# ---------------------------------------------------------------------------
# Student Document
# ---------------------------------------------------------------------------
from .student_document import (  # noqa: F401, E402
    DocumentResponse,
    DocumentUploadRequest,
)

# ---------------------------------------------------------------------------
# Enrollment
# ---------------------------------------------------------------------------
from .enrollment import (  # noqa: F401, E402
    EnrollmentFeeRequest,
    EnrollmentFeeResponse,
)

# ---------------------------------------------------------------------------
# Exam
# ---------------------------------------------------------------------------
from .exam import (  # noqa: F401, E402
    ExamApplyRequest,
    ExamResponse,
    ExamResultRequest,
)

# ---------------------------------------------------------------------------
# Diploma
# ---------------------------------------------------------------------------
from .diploma import (  # noqa: F401, E402
    DiplomaPostRequest,
    DiplomaResponse,
    GraduationPhotoResponse,
)

__all__ = [
    # base
    "APIModel",
    # training
    "TrainingApprovalRequest",
    "TrainingApprovalResponse",
    "TrainingStatus",
    # student document
    "DocumentUploadRequest",
    "DocumentResponse",
    # enrollment
    "EnrollmentFeeRequest",
    "EnrollmentFeeResponse",
    # exam
    "ExamApplyRequest",
    "ExamResultRequest",
    "ExamResponse",
    # diploma
    "DiplomaPostRequest",
    "DiplomaResponse",
    "GraduationPhotoResponse",
]
