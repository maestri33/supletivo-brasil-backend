"""Integracao com o servico `ai` (CONVENTION §7, §14: IA centralizada no app `ai`).

Usa POST /api/v1/json/ que aceita {prompt, schema_description} e devolve
{data: dict}. O `ai` repassa para o provedor (DeepSeek em JSON mode) — aqui nao
sabemos o provedor e nao precisamos saber.

Contrato de correcao:
- Entrada: enunciado da materia (question) + resposta esperada (gabarito) +
  resposta do trainee.
- Saida: {"nota": int 0-10, "justificativa": str pt-br}.

Invariante de negocio: "toda nota gravada tem justificativa" (TODO/PRD §8.4).
Se a IA devolver nota sem justificativa, levantamos IntegrationError; o caller
mantem submission em pending (degrade gracioso).
"""

from dataclasses import dataclass

import httpx

from app.config import get_settings
from app.exceptions import IntegrationError
from app.integrations import BaseClient, request_with_retry

_SCHEMA = (
    "Objeto JSON com exatamente dois campos: "
    "`nota` (numero inteiro de 0 a 10) e `justificativa` (string em portugues "
    "explicando a nota dada com base no que o trainee escreveu vs o gabarito)."
)

_INSTRUCTION = (
    "Voce e' corretor de uma plataforma de treinamento. Compare a resposta do "
    "trainee com o gabarito da materia e atribua uma nota inteira de 0 a 10. "
    "6 ou mais significa aprovado; menor que 6 significa reprovado. "
    "Seja justo, exigente com o conteudo mas tolerante com forma. Responda "
    "APENAS o JSON pedido — sem texto fora dele."
)


@dataclass(frozen=True)
class Grading:
    grade: float
    justification: str


class AIClient(BaseClient):
    async def grade(
        self,
        *,
        question: str,
        expected_answer: str,
        student_answer: str,
    ) -> Grading:
        prompt = (
            f"ENUNCIADO DA MATERIA:\n{question.strip()}\n\n"
            f"GABARITO (resposta esperada):\n{expected_answer.strip()}\n\n"
            f"RESPOSTA DO TRAINEE:\n{student_answer.strip()}"
        )
        body = {
            "prompt": prompt,
            "instruction": _INSTRUCTION,
            "schema_description": _SCHEMA,
            "temperature": 0.2,
        }
        resp = await request_with_retry(self.client, "POST", "/api/v1/json/", json=body)
        payload = resp.json() or {}
        data = payload.get("data") or {}
        try:
            grade = float(data["nota"])
            justification = str(data["justificativa"]).strip()
        except (KeyError, TypeError, ValueError) as exc:
            raise IntegrationError(
                f"Resposta da IA fora do contrato esperado: {data!r}"
            ) from exc
        if not justification:
            raise IntegrationError("IA devolveu nota sem justificativa")
        grade = max(0.0, min(10.0, grade))
        return Grading(grade=grade, justification=justification)


def ai_http_client() -> httpx.AsyncClient:
    s = get_settings()
    return httpx.AsyncClient(base_url=s.ai_base_url, timeout=s.ai_timeout)
