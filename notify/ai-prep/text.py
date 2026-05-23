"""
POST /text/ — geracao de texto via DeepSeek.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.integrations.deepseek import DeepSeekClient
from app.integrations.http_client import get_http_client

router = APIRouter(prefix="/text", tags=["text"])


class TextRequest(BaseModel):
    prompt: str
    instruction: str | None = None
    for_tts: bool = False
    generate_title: bool = False


class TextResponse(BaseModel):
    text: str
    title: str | None = None


@router.post("/", response_model=TextResponse)
async def generate_text(body: TextRequest, client=Depends(get_http_client)):
    ds = DeepSeekClient(client)
    text = await ds.generate_text(
        body.prompt,
        instruction=body.instruction,
        for_tts=body.for_tts,
    )
    title = None
    if body.generate_title:
        title = await ds.title(text)
    return TextResponse(text=text, title=title)
