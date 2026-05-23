from pydantic import BaseModel


class AskRequest(BaseModel):
    question: str
    deep: bool = False


class AskResponse(BaseModel):
    """Resposta do assistente AI."""

    answer: str
    enabled: bool
    model: str | None = None
    elapsed_ms: int | None = None
    tools_called: list[dict] | None = None
    usage: dict | None = None
