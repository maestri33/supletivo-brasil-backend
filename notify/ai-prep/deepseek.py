"""
Cliente DeepSeek — geracao de texto e JSON estruturado.
"""

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


class DeepSeekClient:
    """Cliente para a API do DeepSeek."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        settings = get_settings()
        self._client = client
        self._api_key = settings.deepseek_api_key
        self._base_url = settings.deepseek_base_url
        self._default_model = settings.deepseek_default_model
        self._flash_model = settings.deepseek_flash_model
        self._default_temperature = settings.deepseek_default_temperature

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def _chat(
        self,
        system_prompt: str,
        user_message: str,
        *,
        model: str | None = None,
        temperature: float | None = None,
        json_mode: bool = False,
    ) -> str:
        """Chama a API de chat, retorna o content da resposta."""
        payload: dict = {
            "model": model or self._default_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": temperature if temperature is not None else self._default_temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        resp = await request_with_retry(
            self._client, "POST",
            f"{self._base_url}/chat/completions",
            json=payload,
            headers=self._headers(),
            timeout=60.0,
        )
        if resp.status_code >= 400:
            raise IntegrationError(f"DeepSeek falhou ({resp.status_code}): {resp.text}")

        body = resp.json()
        return body["choices"][0]["message"]["content"]

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    async def generate_text(
        self,
        prompt: str,
        *,
        instruction: str | None = None,
        for_tts: bool = False,
    ) -> str:
        """Gera texto a partir de um prompt."""
        tts_note = (
            "Escreva de forma natural e conversacional, frases curtas. "
            if for_tts else ""
        )
        instruction_line = f"Instrucao adicional: {instruction}" if instruction else ""

        user = f"Prompt: {prompt}\n{instruction_line}"
        result = await self._chat(
            system_prompt=SYSTEM_PROMPT_PT + " " + tts_note,
            user_message=user,
            temperature=0.7,
        )
        text = result.strip().strip('"')
        log.info("deepseek.text_generated", length=len(text))
        return text

    async def generate_json(
        self,
        prompt: str,
        *,
        instruction: str | None = None,
        schema_description: str | None = None,
    ) -> dict:
        """Gera JSON estruturado a partir de um prompt."""
        schema_note = (
            f"O JSON deve seguir este schema: {schema_description}"
            if schema_description else ""
        )
        instruction_line = f"Instrucao: {instruction}" if instruction else ""

        result = await self._chat(
            system_prompt=SYSTEM_PROMPT_PT + " Retorne APENAS um JSON valido. " + schema_note,
            user_message=f"Prompt: {prompt}\n{instruction_line}",
            temperature=0.3,
            json_mode=True,
        )
        try:
            data = json.loads(result)
            log.info("deepseek.json_generated", keys=list(data.keys()))
            return data
        except json.JSONDecodeError:
            log.error("deepseek.json_parse_failed", raw=result[:300])
            raise IntegrationError("Falha ao parsear JSON do DeepSeek")

    async def title(self, text: str) -> str:
        """Gera um titulo curto (max 60 chars)."""
        result = await self._chat(
            system_prompt=SYSTEM_PROMPT_PT + " Retorne apenas o titulo, max 60 caracteres.",
            user_message=f"Titulo para:\n\n{text[:2000]}",
            model=self._flash_model,
        )
        title = result.strip().strip('"')
        log.info("deepseek.title", title=title)
        return title
