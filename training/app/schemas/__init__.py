"""Schemas Pydantic v2 do training.

`APIModel` e' a base de todo schema de entrada/saida (ignora extras, faz trim
de strings). Schemas especificos ficam em modulos por recurso.
"""

from pydantic import BaseModel, ConfigDict


class APIModel(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        str_strip_whitespace=True,
    )


__all__ = ["APIModel"]
