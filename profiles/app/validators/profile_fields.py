"""Validadores de campos de Profile — gênero, tipo sanguíneo, estado civil.

Aceitam None (retorna None) e aliases multilingues.
"""

from app.exceptions import ValidationError

# ── Gender ─────────────────────────────────────────────────────────────

_GENDER_ALIASES = {
    "m": "M",
    "male": "M",
    "masculino": "M",
    "homem": "M",
    "f": "F",
    "female": "F",
    "feminino": "F",
    "mulher": "F",
}

VALID_GENDERS = {"M", "F"}


def validate_gender(value: str | None) -> str | None:
    """Normaliza gênero para M ou F. Aceita aliases. None retorna None."""
    if value is None:
        return None
    if not value:
        return None
    key = value.strip().lower()
    if key in _GENDER_ALIASES:
        return _GENDER_ALIASES[key]
    raise ValidationError(f'Gênero deve ser "M" ou "F", recebido "{value}"')


# ── Blood type ─────────────────────────────────────────────────────────

_BLOOD_ALIASES = {
    "a+": "A+",
    "a positivo": "A+",
    "a-": "A-",
    "a negativo": "A-",
    "b+": "B+",
    "b positivo": "B+",
    "b-": "B-",
    "b negativo": "B-",
    "o+": "O+",
    "o positivo": "O+",
    "o-": "O-",
    "o negativo": "O-",
    "ab+": "AB+",
    "ab positivo": "AB+",
    "ab-": "AB-",
    "ab negativo": "AB-",
}

VALID_BLOOD_TYPES = {"A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-"}


def validate_blood_type(value: str | None) -> str | None:
    """Normaliza tipo sanguíneo. Aceita aliases (a+, A Positivo, etc.). None retorna None."""
    if value is None:
        return None
    if not value:
        return None
    key = value.strip().lower()
    if key in _BLOOD_ALIASES:
        return _BLOOD_ALIASES[key]
    # Fallback: apenas uppercase e valida
    upper = value.upper().strip()
    if upper in VALID_BLOOD_TYPES:
        return upper
    raise ValidationError(
        f'Tipo sanguíneo inválido "{value}". Deve ser um de: {", ".join(sorted(VALID_BLOOD_TYPES))}'
    )


# ── Civil status ───────────────────────────────────────────────────────

_CIVIL_ALIASES = {
    "single": "single",
    "solteiro": "single",
    "solteira": "single",
    "married": "married",
    "casado": "married",
    "casada": "married",
    "widowed": "widowed",
    "viuvo": "widowed",
    "viúvo": "widowed",
    "viuva": "widowed",
    "viúva": "widowed",
    "divorced": "divorced",
    "divorciado": "divorced",
    "divorciada": "divorced",
    "stable_union": "stable_union",
    "uniao_estavel": "stable_union",
    "união_estável": "stable_union",
    "uniao estavel": "stable_union",
    "união estavel": "stable_union",
}

VALID_CIVIL_STATUS = {"single", "married", "widowed", "divorced", "stable_union"}


def validate_civil_status(value: str | None) -> str | None:
    """Normaliza estado civil. Aceita aliases pt-BR. None retorna None."""
    if value is None:
        return None
    if not value:
        return None
    key = value.strip().lower()
    if key in _CIVIL_ALIASES:
        return _CIVIL_ALIASES[key]
    raise ValidationError(
        f'Estado civil inválido "{value}". Deve ser um de: {", ".join(sorted(VALID_CIVIL_STATUS))}'
    )
