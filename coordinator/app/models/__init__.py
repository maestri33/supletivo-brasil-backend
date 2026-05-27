"""Models do coordinator."""

from app.models.coordinator import Coordinator
from app.models.training_approval import TrainingApproval
from app.models.enrollment_fee import EnrollmentFee
from app.models.exam import Exam
from app.models.student_document import StudentDocument
from app.models.diploma import Diploma

__all__ = [
    "Coordinator",
    "TrainingApproval",
    "EnrollmentFee",
    "Exam",
    "StudentDocument",
    "Diploma",
]
