"""Schemas da etapa education — dados educacionais (tabela local).

PRD §4: persistido em `enrollment.educational_data` (próprio do schema, não
delegado). Os 3 campos são OBRIGATÓRIOS por regra do TODO original:
"MUITO IMPORTANTE que este indivíduo diga o último ano que ele estudou,
quando foi; e em que escola foi".
"""

from datetime import date

from pydantic import Field

from app.schemas import APIModel


class EducationGetResponse(APIModel):
    message: str = "Informe sobre seu último ano de estudo"
    last_year_studied: int | None = None
    last_year_date: date | None = None
    last_school: str | None = None


class EducationPostRequest(APIModel):
    last_year_studied: int = Field(
        ...,
        ge=1,
        le=20,
        description="Último ano/série cursado (ex: 9 = 9º ano)",
    )
    last_year_date: date = Field(
        ...,
        description="Data aproximada de quando foi (YYYY-MM-DD)",
    )
    last_school: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="Nome da escola",
    )


class EducationPostResponse(APIModel):
    status: str
    message: str = "Dados educacionais salvos, envie sua selfie"
