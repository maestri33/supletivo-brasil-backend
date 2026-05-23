"""Validação de CEP brasileiro: 8 dígitos, com ou sem hífen."""

import re

from app.exceptions import ValidationError


def validate_zipcode(value: str | None) -> str:
    """Normaliza CEP para 8 dígitos numéricos. Levanta ValidationError se inválido."""
    if value is None or not value:
        raise ValidationError("CEP é obrigatório")

    digits = re.sub(r"[^0-9]", "", value)

    if len(digits) != 8:
        raise ValidationError(
            f"CEP deve ter 8 dígitos, encontrados {len(digits)}",
        )

    if digits == digits[0] * 8:
        raise ValidationError("CEP inválido: todos os dígitos iguais")

    return digits
