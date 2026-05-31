"""Schemas Pydantic do servico auth."""

from pydantic import BaseModel, ConfigDict


class APIModel(BaseModel):
    """Base para todos os schemas de API.

    - extra="ignore": ignora campos desconhecidos (forward compat)
    - str_strip_whitespace=True: limpa whitespace de strings
    """

    model_config = ConfigDict(
        extra="ignore",
        str_strip_whitespace=True,
    )


__all__ = ["APIModel"]
