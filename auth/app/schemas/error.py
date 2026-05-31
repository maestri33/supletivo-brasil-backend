"""Schema de resposta de erro padrao."""

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Resposta padrao de erro para endpoints da API."""

    detail: str
