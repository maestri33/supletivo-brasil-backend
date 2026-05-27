"""
Cliente DeepSeek — geracao de texto e JSON estruturado.
API OpenAI-compatible. Cache de contexto KV ativado por padrao (gratuito).
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
import json

import httpx

from app.config import get_settings
from app.integrations.http_client import IntegrationError, request_with_retry
from app.utils.logging import get_logger

log = get_logger(__name__)

SYSTEM_PROMPT_PT = (
    "Voce responde SEMPRE em portugues brasileiro com acentuacao e pontuacao corretas. "
    "Tom natural, nao-formal, nao-robotico. "
    "NUNCA use {{variavel}} no output. "
    "Sem meta-comentarios, sem aspas, sem markdown."
)


@dataclass
class ChatResult:
    """Metricas de uma chamada ao modelo."""

    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cache_hit_tokens: int = 0
    cache_miss_tokens: int = 0
    finish_reason: str | None = None

    @property
    def cache_hit_rate(self) -> float:
        total_cache = self.cache_hit_tokens + self.cache_miss_tokens
        if total_cache == 0:
            return 0.0
        return self.cache_hit_tokens / total_cache


@dataclass
class StreamChunk:
    """Chunk incremental de stream SSE."""

    content: str = ""
    finish_reason: str | None = None
    usage: dict | None = None


class DeepSeekClient:
    """Cliente para API DeepSeek (/chat/completions)."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        settings = get_settings()
        self._client = client
        self._api_key = settings.deepseek_api_key
        self._base_url = settings.deepseek_base_url
        self._default_model = settings.deepseek_default_model
        self._default_temperature = settings.deepseek_default_temperature
        self._max_tokens = settings.deepseek_max_tokens
        self._user_id = settings.service_name

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _build_payload(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        json_mode: bool = False,
        stream: bool = False,
    ) -> dict:
        payload: dict = {
            "model": model or self._default_model,
            "messages": messages,
            "temperature": temperature
            if temperature is not None
            else self._default_temperature,
            "user_id": self._user_id,
        }
        resolved_max_tokens = max_tokens if max_tokens is not None else self._max_tokens
        if resolved_max_tokens:
            payload["max_tokens"] = resolved_max_tokens
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        if stream:
            payload["stream"] = True
        return payload

    def _extract_result(self, body: dict) -> ChatResult:
        choice = body.get("choices", [{}])[0]
        content: str = choice.get("message", {}).get("content", "")
        usage: dict = body.get("usage", {})

        return ChatResult(
            content=content,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            cache_hit_tokens=usage.get("prompt_cache_hit_tokens", 0),
            cache_miss_tokens=usage.get("prompt_cache_miss_tokens", 0),
            finish_reason=choice.get("finish_reason"),
        )

    async def _chat(
        self,
        system_prompt: str,
        user_message: str,
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> ChatResult:
        payload = self._build_payload(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=json_mode,
        )
        result = await self._request(payload)
        log.info(
            "deepseek.chat_done",
            model=payload["model"],
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            cache_hit=result.cache_hit_tokens,
            cache_miss=result.cache_miss_tokens,
            cache_hit_rate=round(result.cache_hit_rate, 3),
        )
        return result

    # ------------------------------------------------------------------
    # Metodos legados — mantidos para backward compat
    # ------------------------------------------------------------------

    async def generate_text(
        self,
        prompt: str,
        *,
        instruction: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Gera texto natural. Mantido para backward compat com /text/."""
        instruction_line = f"Instrucao adicional: {instruction}" if instruction else ""
        user = f"Prompt: {prompt}\n{instruction_line}"
        result = await self._chat(
            system_prompt=SYSTEM_PROMPT_PT,
            user_message=user,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return result.content.strip().strip('"')

    async def generate_json(
        self,
        prompt: str,
        *,
        instruction: str | None = None,
        schema_description: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict:
        """Gera JSON estruturado. Mantido para backward compat com /json/."""
        schema_note = (
            f"O JSON deve seguir este schema: {schema_description}"
            if schema_description
            else ""
        )
        instruction_line = f"Instrucao: {instruction}" if instruction else ""

        result = await self._chat(
            system_prompt=SYSTEM_PROMPT_PT
            + " Retorne APENAS um JSON valido. "
            + schema_note,
            user_message=f"Prompt: {prompt}\n{instruction_line}",
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=True,
        )
        try:
            data = json.loads(result.content)
            log.info("deepseek.json_parsed", keys=list(data.keys()))
            return data
        except json.JSONDecodeError:
            log.error("deepseek.json_parse_failed", raw=result.content[:300])
            raise IntegrationError("Falha ao parsear JSON do DeepSeek")

    # ------------------------------------------------------------------
    # Novos metodos — retornam ChatResult completo com metricas
    # ------------------------------------------------------------------

    async def _request(self, payload: dict) -> ChatResult:
        resp = await request_with_retry(
            self._client,
            "POST",
            f"{self._base_url}/chat/completions",
            json=payload,
            headers=self._headers(),
            timeout=60.0,
        )
        if resp.status_code >= 400:
            raise IntegrationError(f"DeepSeek falhou ({resp.status_code}): {resp.text}")
        return self._extract_result(resp.json())

    async def chat(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> ChatResult:
        """Chat multi-turn. Messages = [{"role":..., "content":...}]."""
        payload = self._build_payload(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=json_mode,
        )
        result = await self._request(payload)
        log.info(
            "deepseek.chat_done",
            model=payload["model"],
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            cache_hit=result.cache_hit_tokens,
            cache_miss=result.cache_miss_tokens,
            cache_hit_rate=round(result.cache_hit_rate, 3),
        )
        return result

    async def summarize(
        self,
        text: str,
        *,
        format: str = "paragraph",
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> ChatResult:
        """Resume texto no formato especificado: paragraph, bullets, headline."""
        format_prompts = {
            "paragraph": "Resuma o texto em um unico paragrafo coeso e direto:",
            "bullets": "Resuma o texto em topicos com marcadores (•), um por linha:",
            "headline": "Resuma o texto em uma unica manchete jornalistica impactante (max 120 chars):",
        }
        instruction = format_prompts.get(format, format_prompts["paragraph"])
        return await self._chat(
            system_prompt=SYSTEM_PROMPT_PT + " Voce e um especialista em sumarizacao.",
            user_message=f"{instruction}\n\n{text}",
            temperature=temperature if temperature is not None else 0.3,
            max_tokens=max_tokens,
        )

    async def extract(
        self,
        text: str,
        *,
        json_schema: dict,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> ChatResult:
        """Extrai dados estruturados do texto conforme JSON Schema."""
        schema_str = json.dumps(json_schema, ensure_ascii=False)
        return await self._chat(
            system_prompt=(
                SYSTEM_PROMPT_PT
                + f" Extraia do texto os dados conforme este JSON Schema: {schema_str}. "
                + "Retorne APENAS um JSON valido que satisfaca o schema."
            ),
            user_message=text,
            temperature=temperature if temperature is not None else 0.1,
            max_tokens=max_tokens,
            json_mode=True,
        )

    # ------------------------------------------------------------------
    # Streaming (SSE)
    # ------------------------------------------------------------------

    async def chat_stream(
        self,
        messages: list[dict],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Chat multi-turn com streaming. Yield StreamChunk conforme chegam."""
        payload = self._build_payload(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        async with self._client.stream(
            "POST",
            f"{self._base_url}/chat/completions",
            json=payload,
            headers=self._headers(),
            timeout=httpx.Timeout(120.0, read=30.0),
        ) as response:
            if response.status_code >= 400:
                body = await response.aread()
                raise IntegrationError(
                    f"DeepSeek streaming falhou ({response.status_code}): {body.decode()}"
                )

            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str.strip() == "[DONE]":
                    break
                try:
                    chunk_data = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                sc = StreamChunk()
                choices = chunk_data.get("choices", [])
                if choices:
                    delta = choices[0].get("delta", {})
                    sc.content = delta.get("content", "")
                    sc.finish_reason = choices[0].get("finish_reason")
                sc.usage = chunk_data.get("usage")
                yield sc
