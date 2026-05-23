"""Schemas Pydantic para Template."""

from datetime import datetime

from pydantic import BaseModel, Field


class TemplateCreate(BaseModel):
    """Body para criacao de template.

    Informe html OU instruction (sao mutuamente exclusivos).
    Se instruction: usa DeepSeek a partir do template `default` como base.
    """

    slug: str = Field(
        description="Identificador unico (kebab-case) ex: 'welcome', 'checkout', 'receipt'",
        examples=["welcome"],
        pattern=r"^[a-z0-9][a-z0-9\-_]{0,62}[a-z0-9]$",
        min_length=2,
        max_length=64,
    )
    name: str = Field(
        description="Nome legivel para humanos",
        examples=["Boas-vindas"],
        min_length=1,
        max_length=255,
    )
    html: str | None = Field(
        default=None,
        description="HTML completo do template. Use {{title}}, {{content}} e {{service_name}} como placeholders.",
    )
    instruction: str | None = Field(
        default=None,
        description="Instrucao em linguagem natural para a IA (DeepSeek) gerar o template a partir do `default`.",
    )


class TemplateUpdate(BaseModel):
    """Body para atualizacao de template existente.

    Informe html OU instruction. Se nenhum, no-op (retorna o atual).
    """

    name: str | None = Field(
        default=None,
        description="Nome legivel (opcional)",
        max_length=255,
    )
    html: str | None = Field(
        default=None,
        description="HTML completo do template (substitui o atual).",
    )
    instruction: str | None = Field(
        default=None,
        description="Instrucao para a IA editar o HTML atual.",
    )
    is_active: bool | None = Field(
        default=None, description="Liga/desliga template sem deletar.",
    )


class TemplateRead(BaseModel):
    """Representacao de um template persistido."""

    id: int
    slug: str
    name: str
    html: str
    version: int = Field(description="Incrementa a cada atualizacao do HTML")
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TemplateSummary(BaseModel):
    """Versao enxuta sem o HTML — usada em listagem."""

    slug: str
    name: str
    version: int
    is_active: bool
    updated_at: datetime

    model_config = {"from_attributes": True}
