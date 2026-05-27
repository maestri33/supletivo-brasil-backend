"""
Validacao de email — formato, MX, e SMTP handshake.

Fluxo:
  1. Regex — formato RFC 5322 simplificado
  2. DNS MX — verifica se o dominio aceita email
  3. SMTP — tenta RCPT TO no MX (opcional, muitos servidores rejeitam)
"""

import re
import smtplib
import socket
from dataclasses import dataclass, field

import dns.resolver

from app.utils.logging import get_logger
from app.utils.pii import mask_email as _mask_email

log = get_logger(__name__)

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


@dataclass
class EmailValidation:
    email: str
    valid_format: bool = False
    domain: str | None = None
    has_mx: bool = False
    mx_hosts: list[str] = field(default_factory=list)
    smtp_checked: bool = False
    smtp_valid: bool = False
    smtp_detail: str = ""
    is_valid: bool = False


def _check_format(email: str) -> tuple[bool, str | None]:
    m = _EMAIL_RE.match(email)
    if not m:
        return False, None
    domain = email.rsplit("@", 1)[-1].lower()
    return True, domain


def _check_mx(domain: str) -> tuple[bool, list[str]]:
    """Resolve MX records do dominio. Retorna (tem_mx, [hosts_ordenados])."""
    try:
        answers = dns.resolver.resolve(domain, "MX")
        mx_hosts = sorted(
            [str(r.exchange).rstrip(".") for r in answers],
            key=lambda h: next(
                (r.preference for r in answers if str(r.exchange).rstrip(".") == h), 999
            ),
        )
        return bool(mx_hosts), mx_hosts
    except (
        dns.resolver.NoAnswer,
        dns.resolver.NXDOMAIN,
        dns.resolver.NoNameservers,
        dns.exception.Timeout,
    ) as exc:
        log.info("email.mx_not_found", domain=domain, error=str(exc))
        return False, []


def _check_smtp(mx_host: str, email: str, timeout: int = 10) -> tuple[bool, str]:
    """Tenta validar via SMTP RCPT TO. Retorna (valido, detalhe)."""
    try:
        with smtplib.SMTP(mx_host, timeout=timeout) as smtp:
            smtp.helo()
            # Alguns servidores aceitam mail from + rcpt to sem TLS
            smtp.mailfrom("verify@notify.local")
            code, msg = smtp.rcpt(email)
            return code < 400, f"{code} {msg.decode()}"
    except (smtplib.SMTPException, socket.error, OSError) as exc:
        return False, str(exc)


async def validate_email(email: str, *, smtp_check: bool = False) -> EmailValidation:
    """Valida um email: formato, MX, e opcionalmente SMTP.

    Retorna EmailValidation com todos os detalhes.
    """
    result = EmailValidation(email=email)

    # 1. Formato
    ok, domain = _check_format(email)
    if not ok or not domain:
        return result
    result.valid_format = True
    result.domain = domain

    # 2. MX
    has_mx, mx_hosts = _check_mx(domain)
    result.has_mx = has_mx
    result.mx_hosts = mx_hosts

    if not has_mx:
        return result

    # 3. SMTP (opcional — muitos servidores bloqueiam)
    if smtp_check and mx_hosts:
        valid, detail = _check_smtp(mx_hosts[0], email)
        result.smtp_checked = True
        result.smtp_valid = valid
        result.smtp_detail = detail
        result.is_valid = valid
        log.info("email.smtp_checked", email=_mask_email(email), valid=valid, detail=detail)
    else:
        # MX basta para considerar valido
        result.is_valid = has_mx
        log.info("email.validated", email=_mask_email(email), domain=domain, has_mx=has_mx)

    return result
