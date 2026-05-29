"""Schemas Pydantic v2 do enrollment.

`APIModel` é a base de todo schema de entrada/saída (ignora extras, faz trim
de strings). Schemas específicos ficam em módulos por recurso.
"""

from pydantic import BaseModel, ConfigDict


class APIModel(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        str_strip_whitespace=True,
    )


from app.schemas.enrollment import EnrollmentRead  # noqa: E402
from app.schemas.enrollment_event import EnrollmentEventRead, WebhookPayload  # noqa: E402

__all__ = [
    "APIModel",
    "EnrollmentEventRead",
    "EnrollmentRead",
    "WebhookPayload",
]
