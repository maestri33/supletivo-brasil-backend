"""Cliente Mailcow direto — SMTP + API REST (sem service intermediario).

Substitui `app/integrations/smtp.py` (service `mail` Docker) por integracao
direta com o servidor Mailcow (mail.v7m.org). Justificativa:

1. `mail` Docker tinha conflito de credenciais (SMTP_USER/SMTP_PASS divergente
   do notify; `configure_smtp` sobrescrevia config valida com credenciais
   antigas → Mailcow rejeitava `535 auth failed`).
2. Cada chamada via `mail` adiciona um hop extra + 3 retries SMTP internos
   que estouravam o ReadTimeout do notify (mascarando o erro real).
3. Mailcow API REST permite gerenciar app-passwords e mailboxes
   programaticamente (criar uma app-password fresca para o notify, com
   apenas `smtp_access`, e rotacionar quando necessario).

Envio SMTP via STARTTLS na porta 587. `smtplib` e' sincrono — corremos
em thread via `anyio.to_thread.run_sync`.
"""
TODO: mude o nome, pois integracao ficou boa e generica, dá a entender que é um cliente Mailcow, mas na verdade é um cliente SMTP com helpers específicos para Mailcow (API admin). O nome atual é confuso porque sugere que é um cliente específico para Mailcow, mas a parte de envio SMTP é genérica e poderia ser usada com outros servidores. Talvez `SMTPClient` ou `MailServerClient` seja mais apropriado, e os métodos específicos de Mailcow (API admin) podem ser destacados como tal. outrossim,dados fixos tem que estar em ENV

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path
from typing import Any

import anyio
import httpx

from app.config import get_settings
from app.exceptions import IntegrationError
from app.integrations.http_client import request_with_retry
from app.utils.logging import get_logger

log = get_logger(__name__)


def _mask(s: str | None) -> str:
    if not s:
        return ""
    if len(s) <= 4:
        return "***"
    return f"{s[:2]}***{s[-2:]}"


class MailcowSMTPClient:
    """SMTP direto contra Mailcow.

    Construido por request (`MailcowSMTPClient()`) — sem httpx exigido pra
    envio SMTP puro. Passe `http: httpx.AsyncClient` se for usar os helpers
    de API admin (`api_get_mailboxes`, `api_create_app_passwd`, etc.).
    """

    def __init__(self, http: httpx.AsyncClient | None = None) -> None:
        s = get_settings()
        self.host = s.mailcow_smtp_host
        self.port = s.mailcow_smtp_port
        self.user = s.mailcow_smtp_user
        self.password = s.mailcow_smtp_pass
        self.from_email = s.mailcow_from_email or s.mailcow_smtp_user
        self.from_name = s.mailcow_from_name or s.service_name
        self.timeout_s = s.mailcow_timeout_s
        self._http = http
        self._api_url = (s.mailcow_api_url or "").rstrip("/")
        self._api_key = s.mailcow_api_key

    # ── SMTP envio ─────────────────────────────────────────────────────────

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        *,
        plain_body: str | None = None,
        attachments: list[Path] | None = None,
        inline_images: dict[str, tuple[bytes, str]] | None = None,
    ) -> dict[str, Any]:
        """Monta MIME multipart e envia via SMTP+STARTTLS.

        `inline_images` permite embutir imagens no corpo HTML via CID
        (ex: `<img src="cid:notify-img-1">` + dict
        `{"notify-img-1": (bytes, "jpeg")}`). Sem isso o HTML depende de
        URL externa publica — clientes (Gmail) renderizam icone de
        imagem quebrada quando o host nao resolve.

        Retorna dict com `to`, `subject`, `from`, `refused` (lista vazia em
        sucesso). Em erro levanta `IntegrationError`.
        """
        if not self.user or not self.password:
            raise IntegrationError(
                "MAILCOW_SMTP_USER ou MAILCOW_SMTP_PASS nao configurado",
            )

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = formataddr((self.from_name, self.from_email))
        msg["To"] = to_email
        # charset='utf-8' explicito — sem isso o Python EmailMessage tenta
        # us-ascii primeiro e cai em quoted-printable com encoding ambiguo
        # quando ha acentos. Clientes (Gmail, Apple Mail) renderizavam
        # 'informa\\xef\\xbf\\xbdes' em vez de 'informacoes'. Forcar utf-8
        # nas duas partes (plain + html) garante Content-Type header e CTE
        # consistentes.
        msg.set_content(
            plain_body
            or "Este email contem HTML. Use um cliente compativel.",
            charset="utf-8",
        )
        msg.add_alternative(html_body, subtype="html", charset="utf-8")

        # CID inline: anexa imagens relacionadas ao HTML part (o ultimo
        # alternative). Cada `<img src="cid:<key>">` deve casar com uma
        # entrada do dict (sem os angle brackets na chave; o EmailMessage
        # adiciona automaticamente).
        if inline_images:
            html_part = msg.get_payload()[-1]
            for cid, (data, subtype) in inline_images.items():
                html_part.add_related(
                    data,
                    maintype="image",
                    subtype=subtype,
                    cid=f"<{cid}>",
                    disposition="inline",
                )

        for path in attachments or []:
            data = path.read_bytes()
            msg.add_attachment(
                data,
                maintype="application",
                subtype="octet-stream",
                filename=path.name,
            )

        def _send_sync() -> dict[str, Any]:
            with smtplib.SMTP(self.host, self.port, timeout=self.timeout_s) as s:
                s.ehlo()
                s.starttls(context=ssl.create_default_context())
                s.ehlo()
                s.login(self.user, self.password)
                refused = s.send_message(msg)
                return {"refused": refused}

        try:
            result = await anyio.to_thread.run_sync(_send_sync)
        except smtplib.SMTPException as exc:
            err = f"{type(exc).__name__}: {exc!r}"
            log.error(
                "mailcow.smtp_error",
                to=to_email, host=self.host, port=self.port,
                user=_mask(self.user), error=err[:300],
            )
            raise IntegrationError(
                f"Falha SMTP {self.host}:{self.port} -> {to_email}: {err}",
            ) from exc
        except (OSError, TimeoutError) as exc:
            err = f"{type(exc).__name__}: {exc!r}"
            log.error(
                "mailcow.transport_error",
                to=to_email, host=self.host, port=self.port, error=err[:300],
            )
            raise IntegrationError(
                f"Falha transport {self.host}:{self.port} -> {to_email}: {err}",
            ) from exc

        refused = result.get("refused") or {}
        log.info(
            "mailcow.sent",
            to=to_email,
            subject=subject[:80],
            from_email=self.from_email,
            refused_count=len(refused),
        )
        return {
            "to": to_email,
            "subject": subject,
            "from": self.from_email,
            "refused": refused,
        }

    # ── API admin (opcional) ───────────────────────────────────────────────

    def _api_headers(self) -> dict[str, str]:
        if not self._api_key:
            raise IntegrationError("MAILCOW_API_KEY nao configurado")
        return {"X-API-Key": self._api_key, "Content-Type": "application/json"}

    async def _api(self, method: str, path: str, **kw: Any) -> Any:
        if not self._http:
            raise IntegrationError(
                "MailcowSMTPClient precisa de httpx.AsyncClient para "
                "chamadas a API admin",
            )
        if not self._api_url:
            raise IntegrationError("MAILCOW_API_URL nao configurado")
        resp = await request_with_retry(
            self._http,
            method,
            f"{self._api_url}{path}",
            headers=self._api_headers(),
            **kw,
        )
        if resp.status_code >= 400:
            raise IntegrationError(
                f"Mailcow API {method} {path} falhou ({resp.status_code}): "
                f"{resp.text[:200]}",
            )
        return resp.json()

    async def api_list_mailboxes(self) -> list[dict[str, Any]]:
        return await self._api("GET", "/api/v1/get/mailbox/all")

    async def api_list_app_passwords(self, mailbox: str) -> list[dict[str, Any]]:
        return await self._api("GET", f"/api/v1/get/app-passwd/all/{mailbox}")

    async def api_create_app_password(
        self,
        mailbox: str,
        app_name: str,
        password: str,
        *,
        protocols: list[str] | None = None,
    ) -> dict[str, Any]:
        body = {
            "active": "1",
            "username": mailbox,
            "app_name": app_name,
            "app_passwd": password,
            "app_passwd2": password,
            "protocols": protocols or ["smtp_access"],
        }
        return await self._api("POST", "/api/v1/add/app-passwd", json=body)

    async def api_delete_app_password(self, app_pass_id: int) -> dict[str, Any]:
        return await self._api(
            "POST", "/api/v1/delete/app-passwd", json=[app_pass_id],
        )

    async def api_health(self) -> bool:
        """Liveness check trivial — lista mailboxes e confirma 200."""
        try:
            await self.api_list_mailboxes()
            return True
        except IntegrationError:
            return False
