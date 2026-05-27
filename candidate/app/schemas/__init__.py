"""Schemas Pydantic v2 do candidate.

`APIModel` eh a base de todo schema de entrada/saida (ignora extras, faz trim
de strings). Schemas especificos ficam em modulos por recurso.
"""

from pydantic import BaseModel, ConfigDict


class APIModel(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        str_strip_whitespace=True,
    )


class StatusResponse(APIModel):
    """Resposta padrao de avanco de etapa do funil."""

    status: str
    message: str = ""


__all__ = ["APIModel", "StatusResponse"]
