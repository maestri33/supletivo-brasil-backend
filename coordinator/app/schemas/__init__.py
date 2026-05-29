"""Schemas Pydantic para o servico Coordinator (Pydantic 2.8+).

Provas, documentos do aluno e diplomas vivem agora no servico `student`.
"""

from pydantic import BaseModel, ConfigDict


class APIModel(BaseModel):
    """Modelo base Pydantic para schemas de negocio do Coordinator."""

    model_config: ConfigDict = ConfigDict(
        extra="ignore",
        str_strip_whitespace=True,
        from_attributes=True,
    )


from .coordinator import (  # noqa: F401, E402
    CoordinatorCreate,
    CoordinatorResponse,
    CoordinatorUpdate,
)
from .fee import (  # noqa: F401, E402
    EnrollmentFeeCreate,
    EnrollmentFeeListResponse,
    EnrollmentFeePayRequest,
    EnrollmentFeeResponse,
)
from .training import (  # noqa: F401, E402
    TrainingApprovalCreate,
    TrainingApprovalListResponse,
    TrainingApprovalResponse,
    TrainingApprovalUpdate,
)

__all__ = [
    "APIModel",
    "CoordinatorCreate",
    "CoordinatorResponse",
    "CoordinatorUpdate",
    "EnrollmentFeeCreate",
    "EnrollmentFeeListResponse",
    "EnrollmentFeePayRequest",
    "EnrollmentFeeResponse",
    "TrainingApprovalCreate",
    "TrainingApprovalListResponse",
    "TrainingApprovalResponse",
    "TrainingApprovalUpdate",
]
