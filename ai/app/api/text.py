"""
POST /text/ — geracao de texto via DeepSeek.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.integrations.deepseek import DeepSeekClient
from app.integrations.http_client import get_http_client

router = APIRouter(tags=["text"])


class TextRequest(BaseModel):
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
    text: str


@router.post("/", response_model=TextResponse)
async def generate_text(body: TextRequest, client=Depends(get_http_client)):
    ds = DeepSeekClient(client)
    text = await ds.generate_text(
        body.prompt,
        instruction=body.instruction,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
    )
    return TextResponse(text=text)
