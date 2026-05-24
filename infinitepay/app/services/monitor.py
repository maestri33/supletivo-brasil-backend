"""Triagem de anomalias em pagamentos (via app `ai`).

- Triagem rapida (modelo flash) -> json_mode
- Analise profunda (modelo pro) -> chat simples, so quando a flash flagar

Falha silenciosa por design: o monitoramento nunca quebra o fluxo de checkout.
"""

from __future__ import annotations

import json

import structlog

from app.config import get_settings
from app.integrations.ai import AiServiceError, ai_enabled, chat

logger = structlog.get_logger("infinitepay")


async def check_anomaly(external_id: str, payload: dict) -> dict:
    """Triagem rapida (flash). Retorna {alert: bool, reason: str[, deep_analysis]}."""
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
        user_msg = f"external_id: {external_id}\npayload: {json.dumps(payload, default=str)}"
        result = await chat(
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            model=get_settings().ai_model,
            json_mode=True,
            max_tokens=150,
            temperature=0.1,
        )
        parsed = json.loads(result.content or "{}")
        alert = bool(parsed.get("alert", False))
        reason = parsed.get("reason", "")

        if alert:
            deep = await _deep_analysis(external_id, payload, reason)
            return {"alert": True, "reason": reason, "deep_analysis": deep}

        return {"alert": False, "reason": ""}
    except (AiServiceError, json.JSONDecodeError, ValueError) as exc:
        logger.warning("anomaly_check_failed", external_id=external_id, error=str(exc))
        return {"alert": False, "reason": "ai check failed"}


async def _deep_analysis(external_id: str, payload: dict, flash_reason: str) -> str:
    """Analise profunda (modelo pro) quando a triagem flash detecta anomalia."""
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
        result = await chat(
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            model=get_settings().ai_pro_model,
            max_tokens=250,
            temperature=0.3,
        )
        return result.content.strip()
    except AiServiceError as exc:
        logger.warning("deep_anomaly_analysis_failed", external_id=external_id, error=str(exc))
        return ""
