"""Models do coordinator — coordenador, aprovacoes de treinamento e taxas de matricula.

Provas, documentos do aluno e diplomas vivem agora no servico `student`.
"""

from app.models.coordinator import Coordinator
from app.models.enrollment_fee import EnrollmentFee
from app.models.training_approval import TrainingApproval

__all__ = [
    "Coordinator",
    "EnrollmentFee",
    "TrainingApproval",
]
