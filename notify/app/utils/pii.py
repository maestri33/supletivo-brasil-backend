"""PII masking utilities for log output.

COD-18 PII audit: phone and email must never appear in plaintext logs.
Use these helpers to redact PII before passing to structlog.
"""

from __future__ import annotations


def mask_phone(phone: str | None) -> str | None:
    """Redact phone to last 4 digits only.

    >>> mask_phone("5511999998888")
    '****8888'
    >>> mask_phone(None) is None
    True
    """
    if not phone:
        return phone
    if len(phone) <= 4:
        return phone
    return "****" + phone[-4:]


def mask_email(email: str | None) -> str | None:
    """Redact email to first 2 chars of local part + domain.

    >>> mask_email("joao.silva@gmail.com")
    'jo***@gmail.com'
    >>> mask_email(None) is None
    True
    """
    if not email:
        return email
    if "@" not in email:
        return email[:2] + "***" if len(email) > 2 else email
    local, domain = email.split("@", 1)
    visible = local[:2] if len(local) >= 2 else local
    return f"{visible}***@{domain}"
