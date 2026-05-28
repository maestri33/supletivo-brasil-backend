"""
Cliente SMTP direto para envio de email via Mailcow (STARTTLS na porta 587).

Substitui o service `mail` Docker (que conflitava credenciais via
configure_smtp e mascarava 535 como ReadTimeout).
"""

import asyncio
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import get_settings

settings = get_settings()


class SMTPClient:
    """Envio direto STARTTLS:587 com app-password Mailcow."""

    def __init__(self) -> None:
        self._host = settings.mailcow_smtp_host
        self._port = settings.mailcow_smtp_port
        self._user = settings.mailcow_smtp_user
        self._password = settings.mailcow_smtp_pass
        self._timeout = settings.mailcow_timeout_s

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        *,
        plain_body: str | None = None,
        attachments: list | None = None,
        inline_images: list | None = None,
    ) -> dict:
        """Envia email HTML com fallback plain-text opcional.

        Retorna dict com to, subject, from, refused.
        """
        msg = MIMEMultipart("alternative")
        msg["To"] = to_email
        msg["Subject"] = subject
        from_addr = settings.mailcow_from_email or settings.mailcow_smtp_user
        from_name = settings.mailcow_from_name or settings.service_name
        msg["From"] = f"{from_name} <{from_addr}>"

        if plain_body:
            msg.attach(MIMEText(plain_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        refused: dict = {}

        def _send_sync() -> None:
            nonlocal refused
            try:
                with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as srv:
                    srv.starttls()
                    srv.login(self._user, self._password)
                    srv.send_message(msg)
            except smtplib.SMTPRecipientsRefused as exc:
                refused = exc.recipients

        await asyncio.to_thread(_send_sync)

        return {
            "to": to_email,
            "subject": subject,
            "from": f"{from_name} <{from_addr}>",
            "refused": refused,
        }
