"""
Cliente HTTP sync para o servico AI v7m (http://ai:8000/api/v1/text/chat).

Substitui chamadas OpenAI diretas a api.deepseek.com nos cenarios SEM
tool_calling. Os modulos que dependem de tool_calling com DB local
(analytics, reporter) continuam usando o cliente OpenAI direto via
`client.py` — a fronteira arquitetural e' justificada porque os tools
abrem `session_scope()` no DB local do infinitepay.

Fluxo:
- Caller monta `messages` no formato OpenAI ({role, content}).
- chat() faz POST para o AI service, espera envelope APIResponse,
  retorna ChatResult dataclass.
- Em qualquer falha (HTTP, conexao, shape invalido) levanta
  AiServiceError — caller deve ter fallback proprio (como o
  receipt.py atual ja tem).
"""

from dataclasses import dataclass

import httpx

from app.config import get_settings


class AiServiceError(Exception):
    """Falha ao chamar o servico AI v7m."""


@dataclass(frozen=True)
class ChatResult:
    """Resultado de uma chamada chat ao AI service."""

    content: str
    model: str
    finish_reason: str | None
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int


def chat(
    messages: list[dict],
    *,
    model: str | None = None,
    json_mode: bool = False,
    temperature: float | None = None,
    max_tokens: int | None = None,
    timeout: float = 60.0,
) -> ChatResult:
    """POST {ai_base_url}/api/v1/text/chat.

    Args:
        messages: lista no formato OpenAI [{"role": ..., "content": ...}].
        model: override do modelo (ex: "deepseek-v4-flash"). None usa default do AI.
        json_mode: forca response_format=json_object no DeepSeek.
        temperature: 0.0..2.0. None usa default do AI.
        max_tokens: limite de tokens de saida. None deixa AI decidir.
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
        with httpx.Client(timeout=timeout) as http:
            resp = http.post(url, json=payload)
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise AiServiceError(f"chamada ao AI service falhou em {url}: {exc}") from exc

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
        raise AiServiceError(f"shape invalido em response do AI service: {exc}") from exc
