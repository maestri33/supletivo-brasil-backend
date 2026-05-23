"""
Validacao e normalizacao de telefone brasileiro para WhatsApp.

Regras:
- Formato final: 55 + DDD + numero (10 ou 11 digitos)
- Sem o 55: obrigatorio 10 ou 11 digitos
- Se 12 digitos e primeiro for 0: remove o 0 (vira 11)
- Se 11 digitos: terceiro digito (pos 2) tem que ser 9 (movel)
- Fallback WhatsApp: tenta com/sem o 9 dependendo do resultado
"""

import re

import httpx

from app.integrations.whatsapp import WhatsAppClient
from app.utils.logging import get_logger

log = get_logger(__name__)

_NON_DIGIT = re.compile(r"\D")


def _digits(phone: str) -> str:
    return _NON_DIGIT.sub("", phone)


async def _check_whatsapp(phone: str) -> bool:
    """Valida um numero (com 55) no WhatsApp. Retorna True se existe."""
    async with httpx.AsyncClient() as http:
        whatsapp = WhatsAppClient(http)
        try:
            result = await whatsapp.check_numbers([phone])
            return bool(result and isinstance(result[0], dict) and result[0].get("exists"))
        except Exception as exc:
            log.warning("whatsapp.check_failed", phone=phone, error=str(exc))
            return False


async def normalize_and_validate(phone: str) -> str:
    """Normaliza e valida um telefone brasileiro.

    Retorna o numero normalizado (55 + DDD + numero).
    Levanta ValueError se o formato for invalido.
    """
    raw = _digits(phone)

    # Remove 55 se presente
    if raw.startswith("55") and len(raw) > 11:
        raw = raw[2:]

    # Se 12 digitos e primeiro eh 0, remove o 0
    if len(raw) == 12 and raw[0] == "0":
        raw = raw[1:]

    if len(raw) not in (10, 11):
        raise ValueError(
            f"Telefone deve ter 10 ou 11 digitos (sem DDI). Recebido: {len(raw)} digitos"
        )

    # Se 11 digitos, terceiro digito DEVE ser 9
    if len(raw) == 11 and raw[2] != "9":
        raise ValueError(
            "Telefone celular (11 digitos) deve ter 9 como terceiro digito"
        )

    # Valida via WhatsApp com fallback
    full = f"55{raw}"
    valid = await _check_whatsapp(full)

    if not valid and len(raw) == 11:
        # Tenta sem o 9 (fixo)
        without_9 = raw[:2] + raw[3:]
        log.info("phone.trying_without_9", original=raw, attempt=without_9)
        valid = await _check_whatsapp(f"55{without_9}")
        if valid:
            raw = without_9

    if not valid and len(raw) == 10:
        # Tenta com 9 (movel)
        with_9 = raw[:2] + "9" + raw[2:]
        log.info("phone.trying_with_9", original=raw, attempt=with_9)
        valid = await _check_whatsapp(f"55{with_9}")
        if valid:
            raw = with_9

    if not valid:
        raise ValueError(f"Numero nao validado pelo WhatsApp: 55{raw}")

    return f"55{raw}"
