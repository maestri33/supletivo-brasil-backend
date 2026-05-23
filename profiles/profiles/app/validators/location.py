"""Validadores de localização — estado (UF) e cidade."""

import re

from app.exceptions import ValidationError

VALID_UF = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA",
    "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN",
    "RS", "RO", "RR", "SC", "SP", "SE", "TO",
}

_INVISIBLE_RE = re.compile(
    "[​-‏ - ‪-‮⁠-⁩"
    "﻿­᠎͏]"
)
_CONTROL_RE = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")

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

_MULTI_SEP_RE = re.compile(r"[-']{2,}")

_ARTICLES = frozenset({"da", "de", "do", "das", "dos", "e"})


def _capitalizar_palavra(palavra: str) -> str:
    if not palavra:
        return palavra
    return palavra[0].upper() + palavra[1:].lower()


def validate_state(value: str | None) -> str | None:
    """Retorna UF em maiúsculas (2 letras). None ou vazio retorna None."""
    if value is None:
        return None
    if not value:
        return None
    upper = value.upper().strip()
    if len(upper) != 2 or upper not in VALID_UF:
        raise ValidationError(f"Estado inválido \"{value}\". Deve ser uma sigla UF de 2 letras")
    return upper


# ── City ───────────────────────────────────────────────────────────────

def normalize_city(value: str) -> str:
    """Normaliza nome de cidade: trim, invisíveis, colapsa whitespace, Title Case.

    Conectivos locais (da, de, do, das, dos, e) ficam minúsculos.
    Ex: "  sao paulo  " → "São Paulo"
    """
    if not value:
        return ""

    value = _INVISIBLE_RE.sub("", value)
    value = _CONTROL_RE.sub("", value)
    value = re.sub(r"\s+", " ", value)
    value = value.strip()

    if not value:
        return ""

    partes = value.split(" ")
    resultado = []
    for i, parte in enumerate(partes):
        if not parte:
            continue
        if "'" in parte or "-" in parte:
            sub = re.split(r"(['-])", parte)
            parte = "".join(
                seg if seg in ("'", "-") else _capitalizar_palavra(seg)
                for seg in sub
            )
        else:
            parte = _capitalizar_palavra(parte)

        if i > 0 and parte.lower() in _ARTICLES:
            parte = parte.lower()

        resultado.append(parte)

    return " ".join(resultado)


def validate_city(value: str | None) -> str | None:
    """Valida e normaliza nome de cidade. Levanta ValidationError se inválido.

    Regras:
    - None ou vazio permitido
    - Máximo 100 caracteres
    - Pelo menos 2 letras
    - Sem números-only, markup, emojis
    - Sem separadores consecutivos
    """
    if value is None:
        return None
    if not value:
        return None

    value = normalize_city(value)

    if not value:
        return ""

    if len(value) > 100:
        raise ValidationError("Cidade deve ter no máximo 100 caracteres")

    letras = sum(1 for c in value if c.isalpha())
    if letras < 2:
        raise ValidationError("Cidade deve conter pelo menos 2 letras")

    apenas_alfa = "".join(c for c in value if c.isalpha())
    if not apenas_alfa:
        raise ValidationError("Cidade não pode conter apenas números ou símbolos")

    if _SUSPICIOUS_RE.search(value):
        raise ValidationError("Cidade contém caracteres não permitidos (emojis, símbolos, markup)")

    if _MULTI_SEP_RE.search(value):
        raise ValidationError("Cidade contém separadores consecutivos (ex: --, '')")

    return value
