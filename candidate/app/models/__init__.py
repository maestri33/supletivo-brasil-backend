"""Models do schema `candidate` — reexporta p/ popular a metadata (alembic)."""

from app.models.candidate import STATUS_ORDER, Candidate, CandidateStatus

__all__ = ["STATUS_ORDER", "Candidate", "CandidateStatus"]
