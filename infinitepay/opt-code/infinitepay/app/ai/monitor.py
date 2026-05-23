"""
Triagem de anomalias em pagamentos.

Migrado para chamar o AI service v7m via HTTP (sem tool_calling).
- Triagem rapida (flash) -> json_mode
- Analise profunda (pro) -> chat simples, so quando flash flagar

Falha silenciosa por design: monitoring nao deve quebrar checkout flow.
"""

import json
import logging

from app.ai.ai_service_client import AiServiceError, chat
from app.ai.client import ai_enabled

logger = logging.getLogger(__name__)


def check_anomaly(external_id: str, payload: dict) -> dict:
    """Triagem rapida com flash. Retorna {alert: bool, reason: str}."""
    if not ai_enabled():
        return {"alert": False, "reason": "ai disabled"}

    try:
        system_msg = (
            "Analise este pagamento e detecte anomalias. "
            "Responda SOMENTE com JSON valido: "
            '{"alert": false, "reason": ""} ou '
            '{"alert": true, "reason": "motivo curto em pt-BR"}. '
            "Anomalias: valor suspeito, dados inconsistentes, "
            "nome estranho, email invalido aparente."
        )
        user_msg = (
            f"external_id: {external_id}\n"
            f"payload: {json.dumps(payload, default=str)}"
        )
        result = chat(
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            model="deepseek-v4-flash",
            json_mode=True,
            max_tokens=150,
            temperature=0.1,
        )
        parsed = json.loads(result.content or "{}")
        alert = bool(parsed.get("alert", False))
        reason = parsed.get("reason", "")

        if alert:
            deep = _deep_analysis(external_id, payload, reason)
            return {
                "alert": True,
                "reason": reason,
                "deep_analysis": deep,
            }

        return {"alert": False, "reason": ""}
    except (AiServiceError, json.JSONDecodeError, ValueError) as exc:
        logger.warning("anomaly check failed: %s", exc)
        return {"alert": False, "reason": "ai check failed"}


def _deep_analysis(external_id: str, payload: dict, flash_reason: str) -> str:
    """Analise profunda com pro quando flash detecta anomalia."""
    try:
        system_msg = (
            "Voce e um especialista em prevencao a fraudes em pagamentos. "
            "Um sistema de triagem rapida flagou este pagamento como suspeito. "
            "Analise profundamente o payload e explique: "
            "1) Qual o risco real (baixo/medio/alto)? "
            "2) Que padrao especifico de fraude pode ser? "
            "3) Que acao recomenda (ignorar, revisar manualmente, cancelar)? "
            "Responda em pt-BR, maximo 4 frases, tom profissional."
        )
        user_msg = (
            f"Motivo do alerta inicial: {flash_reason}\n"
            f"external_id: {external_id}\n"
            f"payload: {json.dumps(payload, default=str)}"
        )
        result = chat(
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            model="deepseek-v4-pro",
            max_tokens=250,
            temperature=0.3,
        )
        return result.content.strip()
    except AiServiceError as exc:
        logger.warning("deep anomaly analysis failed: %s", exc)
        return ""
