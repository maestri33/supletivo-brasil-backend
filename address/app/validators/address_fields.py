"""Validadores de campos de endereço — kind, UF, country."""

from app.exceptions import ValidationError

VALID_KINDS = {"home", "billing", "shipping"}

_KIND_ALIASES = {
    "home": "home",
    "residencial": "home",
    "casa": "home",
    "billing": "billing",
    "cobranca": "billing",
    "cobrança": "billing",
    "fatura": "billing",
    "shipping": "shipping",
    "entrega": "shipping",
    "envio": "shipping",
}


def validate_kind(value: str | None) -> str:
    if value is None or not value:
        raise ValidationError("kind é obrigatório (home/billing/shipping)")
    key = value.strip().lower()
    if key in _KIND_ALIASES:
        return _KIND_ALIASES[key]
    raise ValidationError(
        f'kind inválido "{value}". Deve ser um de: {", ".join(sorted(VALID_KINDS))}',
    )


VALID_UF = {
    "AC",
    "AL",
    "AP",
    "AM",
    "BA",
    "CE",
    "DF",
    "ES",
    "GO",
    "MA",
    "MT",
    "MS",
    "MG",
    "PA",
    "PB",
    "PR",
    "PE",
    "PI",
    "RJ",
    "RN",
    "RS",
    "RO",
    "RR",
    "SC",
    "SP",
    "SE",
    "TO",
}


def validate_state(value: str | None) -> str:
    if value is None or not value:
        raise ValidationError("state (UF) é obrigatório")
    upper = value.strip().upper()
    if len(upper) != 2 or upper not in VALID_UF:
        raise ValidationError(f'Estado inválido "{value}". Deve ser uma sigla UF de 2 letras')
    return upper


def validate_country(value: str | None) -> str:
    """ISO-3166-1 alpha-2 (2 letras maiúsculas). Default 'BR'."""
    if value is None or not value:
        return "BR"
    upper = value.strip().upper()
    if len(upper) != 2 or not upper.isalpha():
        raise ValidationError(
            f'country inválido "{value}". Use ISO-3166-1 alpha-2 (2 letras, ex: BR)',
        )
    return upper
