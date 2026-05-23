"""Normalização e validação do campo description — texto livre."""

import re

from app.exceptions import ValidationError

# Caracteres invisíveis e de controle (mesmo conjunto do name.py)
_INVISIBLE_RE = re.compile(
    "[​-‏ - ‪-‮⁠-⁩"
    "﻿­᠎͏]"
)
_CONTROL_RE = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")

_MARKUP_RE = re.compile(r"<[^>]*>")

_SUSPICIOUS_RE = re.compile(
    "[{}<>\\[\\]\\\\;`]"
    "|"
    "[\U0001f300-\U0001f9ff"
    "\U0001fa00-\U0001fa6f"
    "\U0001fa70-\U0001fa7c"
    "\U0001fa80-\U0001faaf"
    "\U0001fab0-\U0001fabe"
    "\U0001fac0-\U0001facf"
    "\U0001fad0-\U0001fadf"
    "\U0001fae0-\U0001faef"
    "\U0001faf0-\U0001faff"
    "\U00002600-\U000027bf"
    "\U0001f600-\U0001f64f"
    "\U0001f680-\U0001f6ff"
    "\U0001f900-\U0001f9ff"
    "]"
)

MAX_LENGTH = 2000
MIN_LETTERS = 1


def normalize_description(value: str) -> str:
    """Normaliza texto livre: trim, remove invisíveis, colapsa whitespace."""
    if not value:
        return ""

    value = _INVISIBLE_RE.sub("", value)
    value = _CONTROL_RE.sub("", value)
    value = re.sub(r"\s+", " ", value)
    value = value.strip()

    return value


def validate_description(value: str | None) -> str | None:
    """Valida e normaliza description. Levanta ValidationError se inválido."""
    if value is None:
        return None
    if not value:
        return ""

    value = normalize_description(value)

    if not value:
        return ""

    if len(value) > MAX_LENGTH:
        raise ValidationError(f"Descrição deve ter no máximo {MAX_LENGTH} caracteres")

    if _MARKUP_RE.search(value):
        raise ValidationError("Descrição não pode conter tags HTML/XML")

    if _SUSPICIOUS_RE.search(value):
        raise ValidationError("Descrição contém caracteres não permitidos (emojis, símbolos, markup)")

    apenas_alfa = "".join(c for c in value if c.isalpha())
    if len(apenas_alfa) < MIN_LETTERS:
        raise ValidationError("Descrição deve conter pelo menos 1 letra")

    return value
