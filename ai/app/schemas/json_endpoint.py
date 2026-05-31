"""Schemas de JSON estruturado / DeepSeek JSON mode — endpoints /json/."""

from pydantic import BaseModel, Field


class JSONRequest(BaseModel):
    """Geracao de JSON estruturado via DeepSeek JSON mode."""

    prompt: str = Field(
        description="O que representar como JSON (ex: 'Liste 5 cidades com populacao')"
    )
    instruction: str | None = Field(
        default=None, description="Refinamento (ex: 'Apenas Europa')"
    )
    schema_description: str | None = Field(
        default=None,
        description="Estrutura esperada: 'cidades: array de {nome, populacao, pais}'",
    )
    temperature: float | None = Field(
        default=None, ge=0.0, le=2.0, description="0=consistente, 2=max variacao"
    )
    max_tokens: int | None = Field(
        default=None, description="Limite de tokens na resposta"
    )


class JSONResponse(BaseModel):
    """Resposta JSON estruturada."""

    data: dict
