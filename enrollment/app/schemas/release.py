"""Schemas da etapa release — liberação manual pelo coordenador.

Coordenador insere os "dados da plataforma" (id do aluno na plataforma de
ensino + turma/classe) e o sistema promove a role do matriculando para
`student` no serviço `roles`, encerrando a matrícula em `completed`.
"""

from pydantic import Field

from app.schemas import APIModel


class ReleasePostRequest(APIModel):
    platform_id: str = Field(
        ...,
        min_length=2,
        max_length=80,
        description="Identificador do aluno na plataforma de ensino",
    )
    platform_class: str = Field(
        ...,
        min_length=1,
        max_length=80,
        description="Turma/classe inicial do aluno",
    )
    platform_notes: str | None = Field(
        None,
        max_length=500,
        description="Observações opcionais do coordenador",
    )


class ReleasePostResponse(APIModel):
    status: str
    message: str = "Matrícula liberada. O aluno foi promovido a student."
