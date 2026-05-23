"""Validação dos campos de Educational — nível, série, ano, flags de conclusão."""

from datetime import date

from app.exceptions import ValidationError

VALID_LEVEL = {
    "elementary_incomplete", "elementary_complete",
    "high_school_incomplete", "high_school_complete",
    "higher_incomplete", "higher_complete",
}

VALID_LAST_ELEM = {
    "pre", "1st", "2nd", "3rd", "4th", "5th",
    "6th", "7th", "8th", "9th",
}

VALID_LAST_HS = {"1st_hs", "2nd_hs", "3rd_hs"}

_TRUTHY = frozenset({"true", "1", "yes", "sim"})
_FALSY = frozenset({"false", "0", "no", "não", "nao"})


# ── Boolean normalizer ─────────────────────────────────────────────────

def normalize_boolean(value: str) -> bool | None:
    """Converte string para bool ou None.

    Truthy: true, 1, yes, sim
    Falsy:  false, 0, no, não, nao
    Vazio:  None (campo não informado)
    """
    if not value or not value.strip():
        return None
    v = value.strip().lower()
    if v in _TRUTHY:
        return True
    if v in _FALSY:
        return False
    raise ValidationError(
        f"Valor booleano inválido \"{value}\". Use: true, false, 1, 0, yes, no"
    )


# ── Level ──────────────────────────────────────────────────────────────

def validate_level(value: str) -> str:
    """Valida nível educacional contra LEVEL_CHOICES. Vazio permitido."""
    if value is None:
        return None
    if not value:
        return ""

    v = value.strip().lower()
    if v not in VALID_LEVEL:
        raise ValidationError(
            f"Nível educacional inválido \"{value}\". "
            f"Deve ser um de: {', '.join(sorted(VALID_LEVEL))}"
        )
    return v


# ── Last elementary year ───────────────────────────────────────────────

def validate_last_elementary_year(value: str) -> str:
    """Valida última série do fundamental contra LAST_ELEM_CHOICES. Vazio permitido."""
    if value is None:
        return None
    if not value:
        return ""

    v = value.strip().lower()
    if v not in VALID_LAST_ELEM:
        raise ValidationError(
            f"Série do fundamental inválida \"{value}\". "
            f"Deve ser um de: {', '.join(sorted(VALID_LAST_ELEM))}"
        )
    return v


# ── Last high school year ──────────────────────────────────────────────

def validate_last_high_school_year(value: str) -> str:
    """Valida último ano do médio contra LAST_HS_CHOICES. Vazio permitido."""
    if value is None:
        return None
    if not value:
        return ""

    v = value.strip().lower()
    if v not in VALID_LAST_HS:
        raise ValidationError(
            f"Ano do ensino médio inválido \"{value}\". "
            f"Deve ser um de: {', '.join(sorted(VALID_LAST_HS))}"
        )
    return v


# ── Elementary year ────────────────────────────────────────────────────

def normalize_elementary_year(value: str) -> int | None:
    """Converte string para int ou None. Trata vazio como None."""
    if not value or not value.strip():
        return None
    try:
        return int(value.strip())
    except (ValueError, TypeError):
        raise ValidationError(f"Ano do fundamental inválido: \"{value}\". Deve ser um número inteiro")


def validate_elementary_year(value: str) -> int | None:
    """Valida e normaliza ano do fundamental. Range 1900..ano_atual. None permitido."""
    year = normalize_elementary_year(value)
    if year is None:
        return None
    current = date.today().year
    if year < 1900 or year > current:
        raise ValidationError(
            f"Ano do fundamental deve estar entre 1900 e {current}, recebido {year}"
        )
    return year
