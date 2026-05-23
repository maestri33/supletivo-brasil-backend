"""
POST /json/ — JSON estruturado via DeepSeek JSON mode.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.integrations.deepseek import DeepSeekClient
from app.integrations.http_client import get_http_client

router = APIRouter(tags=["json"])


class JSONRequest(BaseModel):
    prompt: str = Field(description="O que representar como JSON (ex: 'Liste 5 cidades com populacao')")
    instruction: str | None = Field(default=None, description="Refinamento (ex: 'Apenas Europa')")
    schema_description: str | None = Field(default=None, description="Estrutura esperada: 'cidades: array de {nome, populacao, pais}'")
    temperature: float | None = Field(default=None, ge=0.0, le=2.0, description="0=consistente, 2=max variacao")
    max_tokens: int | None = Field(default=None, description="Limite de tokens na resposta")


class JSONResponse(BaseModel):
    data: dict


@router.post("/", response_model=JSONResponse)
async def generate_json(body: JSONRequest, client=Depends(get_http_client)):
    ds = DeepSeekClient(client)
    data = await ds.generate_json(
        body.prompt,
        instruction=body.instruction,
        schema_description=body.schema_description,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
    )
    return JSONResponse(data=data)
