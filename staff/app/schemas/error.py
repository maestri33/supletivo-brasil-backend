"""Schemas de erro do dominio staff."""

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    detail: str = Field(..., description="Codigo de erro ou mensagem curta")
