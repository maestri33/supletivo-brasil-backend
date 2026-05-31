"""Models do schema `training` — reexporta p/ popular a metadata (alembic)."""

from app.models.material import Material
from app.models.submission import Submission, SubmissionStatus
from app.models.trainee import Trainee, TraineeStatus

__all__ = [
    "Material",
    "Submission",
    "SubmissionStatus",
    "Trainee",
    "TraineeStatus",
]
