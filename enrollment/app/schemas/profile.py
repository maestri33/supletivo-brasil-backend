"""Schemas da etapa profile (dados pessoais do matriculando).

Os dados são persistidos no serviço `profiles` (CONVENTION §6 — enrollment
não duplica). Espelha as etapas `personal` + `birth` do candidate, unificadas
numa única chamada já que a matrícula coleta tudo de uma vez.
"""

from datetime import date

from pydantic import Field

from app.schemas import APIModel


class ProfileGetResponse(APIModel):
    message: str = "Preencha seus dados pessoais"
    gender: str | None = None
    mother_name: str | None = None
    father_name: str | None = None
    marital_status: str | None = None
    date_of_birth: date | None = None
    birthplace: str | None = None
    nationality: str | None = None


class ProfilePostRequest(APIModel):
    gender: str = Field(..., min_length=1, max_length=50)
    mother_name: str = Field(..., min_length=2, max_length=120)
    father_name: str = Field(..., min_length=2, max_length=120)
    marital_status: str = Field(..., min_length=2, max_length=50)
    date_of_birth: date = Field(..., description="Data de nascimento (YYYY-MM-DD)")
    birthplace: str = Field(..., min_length=2, max_length=200, description="Cidade/Estado natal")
    nationality: str = Field(..., min_length=2, max_length=100)


class ProfilePostResponse(APIModel):
    status: str
    message: str = "Perfil salvo, preencha seu endereço"
