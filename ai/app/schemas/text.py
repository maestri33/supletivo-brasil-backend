"""Schemas de texto / DeepSeek generica — endpoints /text/ e /v1/text/."""

from pydantic import BaseModel, Field


class TextRequest(BaseModel):
    """Geracao de texto livre."""

    prompt: str = Field(description="Tema ou pergunta principal")
    instruction: str | None = Field(
        default=None, description="Refinamento do comportamento (ex: 'Seja tecnico')"
    )
    temperature: float | None = Field(
        default=None, ge=0.0, le=2.0, description="0=deterministico, 2=max variacao"
    )
    max_tokens: int | None = Field(
        default=None, description="Limite de tokens na resposta"
    )


class TextResponse(BaseModel):
    """Resposta de texto."""

    text: str
