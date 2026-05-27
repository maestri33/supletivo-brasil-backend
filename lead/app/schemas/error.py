"""Schemas de erro do dominio lead."""

from app.schemas.base import APIModel
from pydantic import Field


class ErrorResponse(APIModel):
    detail: str = Field(..., description="Codigo de erro ou mensagem curta")
