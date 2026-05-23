"""Validacao local de CPF e phone — fail fast antes de chamar servicos externos."""

from __future__ import annotations

import re


def validate_cpf(cpf: str) -> str:
    """Valida e normaliza CPF. Retorna o CPF limpo (11 digitos) ou levanta ValueError."""
    clean = re.sub(r"\D", "", cpf)
    if len(clean) != 11:
        raise ValueError(f"CPF deve ter 11 digitos, encontrados {len(clean)}.")
    if clean == clean[0] * 11:
        raise ValueError("CPF nao pode ter todos os digitos iguais.")
    return clean


def validate_phone(phone: str) -> str:
    """Valida e normaliza phone. Retorna phone limpo (10-11 digitos) ou levanta ValueError."""
    clean = re.sub(r"\D", "", phone)
    if len(clean) < 10 or len(clean) > 11:
        raise ValueError(f"Phone deve ter 10 ou 11 digitos, encontrados {len(clean)}.")
    return clean
