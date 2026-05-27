"""Schemas das etapas de perfil (captured, personal, education, birth).

Os dados sao persistidos no servico `profiles` (e o email no `notify`); o
candidate so orquestra e avanca o status.
"""

from datetime import date

from pydantic import EmailStr, Field

from app.schemas import APIModel

# ── captured ────────────────────────────────────────────────────────────────


class CapturedGetResponse(APIModel):
    message: str = "Insira seus dados para prosseguir"
    name: str | None = None
    phone: str | None = None
    email: str | None = None


class CapturedPostRequest(APIModel):
    name: str = Field(..., min_length=2, max_length=120)
    email: EmailStr


class CapturedPostResponse(APIModel):
    status: str
    message: str = "Dados salvos, preencha dados pessoais"
    name: str | None = None
    phone: str | None = None
    email: str | None = None


# ── personal ────────────────────────────────────────────────────────────────


class PersonalGetResponse(APIModel):
    message: str = "Preencha seus dados pessoais"
    gender: str | None = None
    mother_name: str | None = None
    father_name: str | None = None
    marital_status: str | None = None


class PersonalPostRequest(APIModel):
    gender: str = Field(..., min_length=1, max_length=50)
    mother_name: str = Field(..., min_length=2, max_length=120)
    father_name: str = Field(..., min_length=2, max_length=120)
    marital_status: str = Field(..., min_length=2, max_length=50)


class PersonalPostResponse(APIModel):
    status: str
    message: str = "Dados pessoais salvos, preencha dados educacionais"


# ── educational ─────────────────────────────────────────────────────────────


class EducationalGetResponse(APIModel):
    message: str = "Preencha seus dados educacionais"
    education_level: str | None = None
    institution: str | None = None
    course: str | None = None
    completion_year: int | None = None


class EducationalPostRequest(APIModel):
    education_level: str = Field(..., min_length=2, max_length=100)
    institution: str = Field(..., min_length=2, max_length=200)
    course: str | None = Field(None, max_length=200)
    completion_year: int | None = Field(None, ge=1950, le=2100)


class EducationalPostResponse(APIModel):
    status: str
    message: str = "Dados educacionais salvos, preencha dados de nascimento"


# ── birth ───────────────────────────────────────────────────────────────────


class BirthGetResponse(APIModel):
    message: str = "Preencha seus dados de nascimento"
    date_of_birth: date | None = None
    birthplace: str | None = None
    nationality: str | None = None


class BirthPostRequest(APIModel):
    date_of_birth: date = Field(..., description="Data de nascimento")
    birthplace: str = Field(..., min_length=2, max_length=200, description="Cidade/Estado natal")
    nationality: str = Field(..., min_length=2, max_length=100, description="Nacionalidade")


class BirthPostResponse(APIModel):
    status: str
    message: str = "Dados de nascimento salvos, preencha o endereco"
