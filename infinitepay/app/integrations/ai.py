"""Client do app `ai` central (http://ai:8000/api/v1/text/chat).

§12: a IA e dona do app `ai`; aqui so replicamos a logica de chamada (sem
integrar DeepSeek direto). Usado por services/receipt.py e services/monitor.py
para gerar texto sem tool_calling. Qualquer falha vira AiServiceError — o caller
sempre tem fallback (o checkout nunca quebra por causa da IA).
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.config import get_settings


class AiServiceError(Exception):
    """Falha ao chamar o app `ai` central."""


@dataclass(frozen=True)
class ChatResult:
    """Resultado de uma chamada chat ao app `ai`."""

    content: str
    model: str
    finish_reason: str | None
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int


def ai_enabled() -> bool:
    """A IA colaborativa (recibo + triagem) so roda se habilitada no .env."""
    return get_settings().ai_features_enabled


async def chat(
    messages: list[dict],
    *,
    model: str | None = None,
    json_mode: bool = False,
    temperature: float | None = None,
    max_tokens: int | None = None,
    timeout: float = 60.0,  # noqa: ASYNC109 — timeout do httpx (mecanismo correto p/ HTTP)
) -> ChatResult:
    """POST {ai_base_url}/api/v1/text/chat.

    Args:
        messages: lista no formato OpenAI [{"role": ..., "content": ...}].
        model: override do modelo. None deixa o app `ai` decidir.
        json_mode: forca response_format=json_object no modelo.
        temperature: 0.0..2.0. None usa o default do app `ai`.
        max_tokens: limite de tokens de saida. None deixa o app `ai` decidir.
        timeout: timeout total em segundos para a chamada HTTP.

    Raises:
        AiServiceError: qualquer falha HTTP, conexao ou shape invalido.
    """
    settings = get_settings()

    payload: dict = {"messages": messages, "json_mode": json_mode}
    if model is not None:
        payload["model"] = model
    if temperature is not None:
        payload["temperature"] = temperature
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens

    url = f"{settings.ai_base_url.rstrip('/')}/api/v1/text/chat"

    try:
        async with httpx.AsyncClient(timeout=timeout) as http:
            resp = await http.post(url, json=payload)
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise AiServiceError(f"chamada ao app `ai` falhou em {url}: {exc}") from exc

    try:
        body = resp.json()
        return ChatResult(
            content=body["data"]["message"]["content"],
            model=body["model"],
            finish_reason=body.get("finish_reason"),
            latency_ms=body.get("latency_ms", 0.0),
            prompt_tokens=body.get("usage", {}).get("prompt_tokens", 0),
            completion_tokens=body.get("usage", {}).get("completion_tokens", 0),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise AiServiceError(f"shape invalido na resposta do app `ai`: {exc}") from exc
