"""PII masking utilities for log output.

COD-18 PII audit: sensitive document fields must never appear in plaintext logs.
"""
from __future__ import annotations


def mask_number(value: str | None) -> str | None:
    """Redact document/ID numbers to last 4 digits only.

    >>> mask_number("12345678901")
    '****8901'
    >>> mask_number(None) is None
    True
    >>> mask_number("AB")
    'AB'
    """
    if not value:
        return value
    if len(value) <= 4:
        return value
    return "****" + value[-4:]
