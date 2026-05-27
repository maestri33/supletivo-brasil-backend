"""Validação de data de nascimento — normalização e validação (16+ anos)."""

from datetime import date

from app.exceptions import ValidationError


def normalize_birth_date(value: str) -> date | None:
    """Converte string ISO para date. Vazio retorna None. Formato inválido levanta erro."""
    if not value or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip())
    except (ValueError, TypeError):
        raise ValidationError(
            f'Data de nascimento inválida "{value}". Use o formato ISO 8601 (YYYY-MM-DD)'
        )


def validate_birth_date(value: date) -> date:
    """Valida data de nascimento: deve estar no passado e idade >= 16."""
    today = date.today()

    if value >= today:
        raise ValidationError("Data de nascimento deve estar no passado")

    age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
    if age < 16:
        raise ValidationError("Deve ter pelo menos 16 anos")

    return value
