"""Validação de CPF — remove formatação, valida dígitos verificadores."""

import re

from app.exceptions import ValidationError


def validate_cpf(cpf: str) -> str:
    """Valida e normaliza uma string de CPF. Retorna apenas dígitos. Levanta ValidationError se inválido."""
    if not cpf:
        raise ValidationError("CPF é obrigatório")

    digits = re.sub(r"[^0-9]", "", cpf)

    if len(digits) != 11:
        raise ValidationError(f"CPF deve ter 11 dígitos, encontrados {len(digits)}")

    if digits == digits[0] * 11:
        raise ValidationError("CPF inválido: todos os dígitos iguais")

    def _dv(nums: str, factor: int) -> int:
        total = sum(int(d) * (factor - i) for i, d in enumerate(nums[: factor - 1]))
        remainder = total % 11
        return 0 if remainder < 2 else 11 - remainder

    dv1 = _dv(digits, 10)
    if dv1 != int(digits[9]):
        raise ValidationError("CPF inválido: primeiro dígito verificador não confere")

    dv2 = _dv(digits, 11)
    if dv2 != int(digits[10]):
        raise ValidationError("CPF inválido: segundo dígito verificador não confere")

    return digits
