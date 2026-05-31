"""
Cliente de envio de email.

Dois caminhos suportados, escolhidos automaticamente pela config:

1. **Mailcow via SSH + sendmail** (preferido — preserva DKIM/SPF/DMARC do
   dominio v7m.org). Ativo quando `settings.mailcow_ssh_host` esta preenchido.
   Abre SSH no host do Mailcow (VM 150) e injeta a mensagem direto no Postfix
   do container atraves de `docker exec -i ... sendmail -t -f <from>`.

2. **SMTP direto STARTTLS:587** (fallback / relay externo tipo Gmail). Ativo
   quando `settings.mailcow_ssh_host` vazio e `settings.mailcow_smtp_host`
   preenchido. Mesma classe, mesma API publica.

A escolha eh dinamica: troque `MAILCOW_SSH_HOST` no .env e reinicie o
container — sem mudar codigo.
"""

import asyncio
import shlex
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import get_settings

settings = get_settings()


class SMTPClient:
    """Envio de email via Mailcow-SSH (preferido) ou SMTP STARTTLS (fallback)."""

    def __init__(self) -> None:
        # Mailcow via SSH
        self._ssh_host = settings.mailcow_ssh_host
        self._ssh_key = settings.mailcow_ssh_key
        self._postfix_container = settings.mailcow_postfix_container
        # SMTP direto (fallback)
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

        if self._ssh_host:
            await self._send_via_ssh(msg, from_addr)
        else:
            refused = await self._send_via_smtp(msg)

        return {
            "to": to_email,
            "subject": subject,
            "from": f"{from_name} <{from_addr}>",
            "refused": refused,
        }

    # ------------------------------------------------------------------
    # Mailcow SSH + sendmail
    # ------------------------------------------------------------------
    async def _send_via_ssh(self, msg: MIMEMultipart, from_addr: str) -> None:
        """Envia via ssh root@mail-vm 'docker exec ... sendmail'.

        A authorized_keys da VM Mailcow restringe a key a um command= fixo
        (sendmail -t -f noreply@v7m.org), entao o comando remoto que passamos
        eh ignorado em favor daquele. Mantemos um placeholder valido pra nao
        gerar warnings.
        """
        raw = msg.as_bytes()
        remote_cmd = (
            f"docker exec -i {shlex.quote(self._postfix_container)} "
            f"sendmail -t -f {shlex.quote(from_addr)}"
        )
        ssh_args = [
            "ssh",
            "-i", self._ssh_key,
            "-o", "BatchMode=yes",
            "-o", "ConnectTimeout=5",
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", "UserKnownHostsFile=/root/.ssh/known_hosts",
            self._ssh_host,
            remote_cmd,
        ]
        proc = await asyncio.create_subprocess_exec(
            *ssh_args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=raw),
                timeout=self._timeout,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise RuntimeError(
                f"ssh+sendmail timeout apos {self._timeout}s para {self._ssh_host}"
            )
        if proc.returncode != 0:
            err = (stderr or b"").decode("utf-8", errors="replace").strip()
            raise RuntimeError(
                f"ssh+sendmail exit={proc.returncode}: {err or '<sem stderr>'}"
            )

    # ------------------------------------------------------------------
    # SMTP STARTTLS direto (fallback)
    # ------------------------------------------------------------------
    async def _send_via_smtp(self, msg: MIMEMultipart) -> dict:
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
        return refused
