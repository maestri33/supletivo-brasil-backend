from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class UsageStats(BaseModel):
    """Metricas de uso de tokens e cache."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    cache_hit_tokens: int = 0
    cache_miss_tokens: int = 0


class APIResponse(BaseModel, Generic[T]):
    """Envelope padrao para todas as respostas v1."""

    provider: str
    model: str
    latency_ms: float
    usage: UsageStats = Field(default_factory=UsageStats)
    finish_reason: str | None = None
    data: T


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None)
    stream: bool = Field(default=False)
    model: str | None = Field(
        default=None,
        description="Override do modelo. Se None, usa deepseek_default_model. Ex: 'deepseek-v4-flash' para tarefas rapidas.",
    )
    json_mode: bool = Field(
        default=False,
        description="Forca response_format=json_object no DeepSeek. O cliente deve garantir que o system prompt instrua o modelo a retornar JSON.",
    )


class ChatData(BaseModel):
    message: ChatMessage
