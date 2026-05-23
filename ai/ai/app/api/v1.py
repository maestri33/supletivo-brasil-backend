"""
Endpoints v1 — contratos novos com envelope APIResponse.
"""

import json
import time

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.api.schemas import (
    APIResponse,
    ChatData,
    ChatMessage,
    ChatRequest,
    ExtractData,
    ExtractRequest,
    SummarizeData,
    SummarizeRequest,
    UsageStats,
)
from app.config import get_settings
from app.integrations.deepseek import DeepSeekClient
from app.integrations.http_client import get_http_client

router = APIRouter(tags=["v1"])


def _envelope(provider: str, model: str, latency_ms: float, usage: UsageStats, finish_reason: str | None, data):
    return APIResponse(
        provider=provider,
        model=model,
        latency_ms=round(latency_ms, 2),
        usage=usage,
        finish_reason=finish_reason,
        data=data,
    )


# ---------------------------------------------------------------------------
# POST /v1/text/chat
# ---------------------------------------------------------------------------

@router.post("/text/chat")
async def chat(body: ChatRequest, client=Depends(get_http_client)):
    settings = get_settings()
    ds = DeepSeekClient(client)
    model = body.model or settings.deepseek_default_model

    if not body.stream:
        t0 = time.monotonic()
        result = await ds.chat(
            [m.model_dump() for m in body.messages],
            model=model,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
            json_mode=body.json_mode,
        )
        latency = (time.monotonic() - t0) * 1000
        return _envelope(
            provider="deepseek", model=model, latency_ms=latency,
            usage=UsageStats(
                prompt_tokens=result.prompt_tokens,
                completion_tokens=result.completion_tokens,
                cache_hit_tokens=result.cache_hit_tokens,
                cache_miss_tokens=result.cache_miss_tokens,
            ),
            finish_reason=result.finish_reason,
            data=ChatData(message=ChatMessage(role="assistant", content=result.content)),
        )

    # --- Stream SSE ---
    # Nota: model override e json_mode nao sao suportados no stream atualmente.
    # Stream sempre usa deepseek_default_model. Adicione em chat_stream() se necessario.
    async def sse_generator():
        t0 = time.monotonic()
        first_token_time = None
        yield f"data: {json.dumps({'type': 'meta', 'provider': 'deepseek', 'model': model})}\n\n"

        async for chunk in ds.chat_stream(
            [m.model_dump() for m in body.messages],
            temperature=body.temperature,
            max_tokens=body.max_tokens,
        ):
            if chunk.content:
                if first_token_time is None:
                    first_token_time = time.monotonic()
                yield f"data: {json.dumps({'type': 'delta', 'content': chunk.content})}\n\n"

            if chunk.finish_reason or chunk.usage:
                ttft_ms = round(((first_token_time or t0) - t0) * 1000, 2)
                yield f"data: {json.dumps({'type': 'finish', 'finish_reason': chunk.finish_reason, 'usage': chunk.usage, 'ttft_ms': ttft_ms})}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


# ---------------------------------------------------------------------------
# POST /v1/text/summarize
# ---------------------------------------------------------------------------

@router.post("/text/summarize")
async def summarize(body: SummarizeRequest, client=Depends(get_http_client)):
    settings = get_settings()
    ds = DeepSeekClient(client)
    model = settings.deepseek_default_model

    t0 = time.monotonic()
    result = await ds.summarize(
        body.text,
        format=body.format.value,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
    )
    latency = (time.monotonic() - t0) * 1000
    return _envelope(
        provider="deepseek", model=model, latency_ms=latency,
        usage=UsageStats(
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            cache_hit_tokens=result.cache_hit_tokens,
            cache_miss_tokens=result.cache_miss_tokens,
        ),
        finish_reason=result.finish_reason,
        data=SummarizeData(summary=result.content.strip()),
    )


# ---------------------------------------------------------------------------
# POST /v1/text/extract
# ---------------------------------------------------------------------------

@router.post("/text/extract")
async def extract(body: ExtractRequest, client=Depends(get_http_client)):
    settings = get_settings()
    ds = DeepSeekClient(client)
    model = settings.deepseek_default_model

    t0 = time.monotonic()
    result = await ds.extract(
        body.text,
        json_schema=body.json_schema,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
    )
    latency = (time.monotonic() - t0) * 1000

    try:
        extracted = json.loads(result.content)
    except json.JSONDecodeError:
        from app.integrations.http_client import IntegrationError
        raise IntegrationError("Falha ao parsear JSON da extracao")

    return _envelope(
        provider="deepseek", model=model, latency_ms=latency,
        usage=UsageStats(
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            cache_hit_tokens=result.cache_hit_tokens,
            cache_miss_tokens=result.cache_miss_tokens,
        ),
        finish_reason=result.finish_reason,
        data=ExtractData(extracted=extracted),
    )
