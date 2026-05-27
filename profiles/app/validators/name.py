"""Normalização e validação de nomes de pessoa.

Camadas independentes:
  normalize_name   — limpeza e capitalização (sempre aplicada)
  validate_name    — regras de domínio e segurança (rejeita inválidos)
  canonicalize_name — representação interna para dedup/busca (não afeta display)
"""

import re
import unicodedata

from app.exceptions import ValidationError

# ── Constantes ──────────────────────────────────────────────────────────

_CONECTORES = frozenset({"da", "de", "do", "das", "dos", "e"})

_BLACKLIST = frozenset(
    {
        "admin",
        "administrador",
        "suporte",
        "support",
        "system",
        "sistema",
        "root",
        "null",
        "undefined",
        "test",
        "teste",
        "user",
        "usuario",
        "usuário",
        "ninguem",
        "ninguém",
        "anonimo",
        "anônimo",
        "anonymous",
        "cliente",
        "cliente1",
        "visitante",
    }
)

# Caracteres invisíveis ou perigosos que devem ser removidos
_INVISIBLE_RE = re.compile(
    "[​-‏"  # zero-width space, ZW non-joiner, ZW joiner, LRM, RLM
    " - "  # line/paragraph separator
    "‪-‮"  # bidirectional overrides
    "⁠-⁩"  # word joiner, invisible operators, directional isolates
    "﻿"  # BOM / ZW no-break space
    "­"  # soft hyphen
    "᠎"  # mongolian vowel separator
    "͏"  # combining grapheme joiner
    "]"
)

# Caracteres de controle (exceto whitespace comum)
_CONTROL_RE = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")

# Múltiplos separadores consecutivos (hífen, apóstrofo)
_MULTI_SEP_RE = re.compile(r"[-']{2,}")

# Símbolos suspeitos: emojis, markup, SQL-ish, excesso de pontuação
_SUSPICIOUS_RE = re.compile(
    "[<>{}\\[\\]\\\\;`]"  # markup / SQL-ish
    "|"  # OR
    "[\U0001f300-\U0001f9ff"  # emojis diversos
    "\U0001fa00-\U0001fa6f"
    "\U0001fa70-\U0001fa7c"
    "\U0001fa80-\U0001faaf"
    "\U0001fab0-\U0001fabe"
    "\U0001fac0-\U0001facf"
    "\U0001fad0-\U0001fadf"
    "\U0001fae0-\U0001faef"
    "\U0001faf0-\U0001faff"
    "\U00002600-\U000027bf"  # misc symbols
    "\U0001f600-\U0001f64f"  # emoticons
    "\U0001f680-\U0001f6ff"  # transport
    "\U0001f900-\U0001f9ff"  # supplemental symbols
    "]"
)


# ── Helpers ─────────────────────────────────────────────────────────────


def _tem_letras_suficientes(nome: str, minimo: int = 2) -> bool:
    """Pelo menos N caracteres classificados como letra (qualquer alfabeto)."""
    return sum(1 for c in nome if c.isalpha()) >= minimo


def _entropia_baixa(nome: str) -> bool:
    """Detecta repetição excessiva ou padroes sem sentido (aaaaaa, ababab, ...)."""
    clean = re.sub(r"\s+", "", nome).lower()
    if not clean:
        return False

    # Strings muito curtas: todos caracteres iguais (aa, bb)
    if len(clean) <= 2:
        return len(set(clean)) == 1

    # Mais de 50% dos caracteres iguais
    freq = {}
    for c in clean:
        freq[c] = freq.get(c, 0) + 1
    if max(freq.values()) / len(clean) > 0.5:
        return True

    # Padrão periódico: ababab, abcabc, xyxyxy
    n = len(clean)
    for period in range(1, n // 2 + 1):
        if n % period == 0 and clean == clean[:period] * (n // period):
            return True

    return False


def _capitalizar_palavra(palavra: str) -> str:
    """Primeira letra maiúscula, resto minúsculo."""
    if not palavra:
        return palavra
    return palavra[0].upper() + palavra[1:].lower()


# ── Normalização ────────────────────────────────────────────────────────


def normalize_name(nome: str) -> str:
    """Pipeline completo de normalização de nome próprio.

    Ordem:
    1. Unicode NFC
    2. Remove caracteres invisíveis e de controle
    3. Colapsa whitespace (espaços, tabs, newlines, unicode spaces)
    4. Trim
    5. Capitalização inteligente (conectivos minúsculos, apóstrofos)
    """
    if not nome:
        return ""

    # 1. Unicode NFC — normaliza combinados (João → João)
    nome = unicodedata.normalize("NFC", nome)

    # 2. Remove invisíveis e controles
    nome = _INVISIBLE_RE.sub("", nome)
    nome = _CONTROL_RE.sub("", nome)

    # 3. Colapsa qualquer whitespace para espaço simples
    nome = re.sub(r"\s+", " ", nome)

    # 4. Trim
    nome = nome.strip()

    if not nome:
        return ""

    # 5. Capitalização inteligente
    partes = nome.split(" ")
    resultado = []
    for i, parte in enumerate(partes):
        if not parte:
            continue

        # Capitaliza segmentos delimitados por apóstrofo ou hífen
        # Ex: D'Ávila, Ana-Clara, O'Connor
        if "'" in parte or "-" in parte:
            sub = re.split(r"(['-])", parte)
            parte = "".join(seg if seg in ("'", "-") else _capitalizar_palavra(seg) for seg in sub)
        else:
            parte = _capitalizar_palavra(parte)

        # Conectivos minúsculos (exceto primeira palavra)
        if i > 0 and parte.lower() in _CONECTORES:
            parte = parte.lower()

        resultado.append(parte)

    return " ".join(resultado)


# ── Validação ───────────────────────────────────────────────────────────


def validate_name(nome: str | None) -> str | None:
    """Valida e normaliza nome. Levanta ValidationError se inválido.

    Regras:
    - None ou vazio é permitido (campo opcional)
    - Máximo 120 caracteres
    - Pelo menos 2 letras unicode
    - Não pode ser apenas números
    - Bloqueia caracteres suspeitos (emojis, markup, SQL-ish)
    - Bloqueia múltiplos separadores consecutivos (---, ''')
    - Bloqueia blacklist contextual (admin, root, etc.)
    - Bloqueia nonsense (repetição, baixa entropia)
    """
    if nome is None:
        return None
    if not nome:
        return ""

    # Normaliza primeiro
    nome = normalize_name(nome)

    if not nome:
        return ""

    # Tamanho máximo
    if len(nome) > 120:
        raise ValidationError("Nome deve ter no máximo 120 caracteres")

    # Pelo menos 2 letras reais
    if not _tem_letras_suficientes(nome, minimo=2):
        raise ValidationError("Nome deve conter pelo menos 2 letras")

    # Não pode ser apenas números (ex: "12345")
    apenas_alfa = "".join(c for c in nome if c.isalpha())
    if not apenas_alfa:
        raise ValidationError("Nome não pode conter apenas números ou símbolos")

    # Caracteres suspeitos
    if _SUSPICIOUS_RE.search(nome):
        raise ValidationError("Nome contém caracteres não permitidos (emojis, símbolos, markup)")

    # Múltiplos separadores
    if _MULTI_SEP_RE.search(nome):
        raise ValidationError("Nome contém separadores consecutivos (ex: --, '')")

    # Blacklist contextual
    normalized_lower = nome.strip().lower()
    if normalized_lower in _BLACKLIST:
        raise ValidationError(f'Nome "{nome}" não é permitido')

    # Nonsense / baixa entropia
    if _entropia_baixa(nome):
        raise ValidationError("Nome parece inválido (repetição excessiva ou baixa entropia)")

    return nome


# ── Canonicalização ─────────────────────────────────────────────────────


def canonicalize_name(nome: str) -> str:
    """Representação canônica para deduplicação, busca e matching.

    Remove acentos, lowercase, sem espaços.
    Ex: "Víctor Maéstri" → "victormaestri"
    """
    if not nome:
        return ""
    nome = unicodedata.normalize("NFKD", nome)
    nome = "".join(c for c in nome if not unicodedata.combining(c))
    nome = nome.lower()
    nome = re.sub(r"\s+", "", nome)
    return nome
