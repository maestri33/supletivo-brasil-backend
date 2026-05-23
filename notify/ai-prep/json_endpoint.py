"""
POST /json/ — JSON estruturado via DeepSeek JSON mode.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.integrations.deepseek import DeepSeekClient
from app.integrations.http_client import get_http_client

router = APIRouter(prefix="/json", tags=["json"])


class JSONRequest(BaseModel):
    prompt: str
    instruction: str | None = None
    schema_description: str | None = None


class JSONResponse(BaseModel):
    data: dict


@router.post("/", response_model=JSONResponse)
async def generate_json(body: JSONRequest, client=Depends(get_http_client)):
    ds = DeepSeekClient(client)
    data = await ds.generate_json(
        body.prompt,
        instruction=body.instruction,
        schema_description=body.schema_description,
    )
    return JSONResponse(data=data)
