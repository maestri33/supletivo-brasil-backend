"""
Cliente REST para a API Mailcow (https://mail.v7m.org/api/v1/).

Gerencia dominios, mailboxes, aliases, DKIM e fila Postfix via API admin.

Auth: header X-API-Key (Settings.mailcow_api_key).
Base URL: Settings.mailcow_api_url.

Endpoints implementados:
  Dominios:
    - list_domains()          — GET /get/domain/all
    - get_domain(domain)      — GET /get/domain/{domain}
    - create_domain(...)      — POST /add/domain
    - edit_domain(...)        — POST /edit/domain
    - delete_domain(domain)   — POST /delete/domain
  Mailboxes:
    - list_mailboxes(domain)  — GET /get/mailbox/{domain}
    - get_mailbox(addr)       — GET /get/mailbox/{addr}
    - create_mailbox(...)     — POST /add/mailbox
    - edit_mailbox(...)       — POST /edit/mailbox
    - delete_mailbox(addr)    — POST /delete/mailbox
  Aliases:
    - list_aliases()          — GET /get/alias/all
    - create_alias(...)       — POST /add/alias
    - delete_alias(alias_id)  — POST /delete/alias
  DKIM:
    - get_dkim(domain)        — GET /get/dkim/{domain}
    - generate_dkim(domain)   — POST /add/dkim/{domain}
  Fila Postfix:
    - get_queue()             — GET /get/postfix/queue/all
    - flush_queue()           — POST /edit/postfix/queue/flush
  Logs:
    - get_logs(...)           — GET /get/logs/all
  Health:
    - health()                — GET / (verifica conectividade + API key)
    - status()                — Status agregado: dominios, mailboxes, queue

Seguranca:
  - NUNCA loga API key ou senhas.
  - Operacoes destrutivas (delete) exigem confirmacao explicita via
    param `confirm=True`, senao levanta ValueError.
"""

from typing import Any

import httpx

from app.config import get_settings
from app.exceptions import IntegrationError
from app.integrations.http_client import request_with_retry
from app.utils.logging import get_logger

log = get_logger(__name__)

# Sentinel para operacoes destrutivas
_CONFIRM_REQUIRED = (
    "Operacao destrutiva. Passe confirm=True para confirmar. "
    "Acao irreversivel."
)


class MailcowClient:
    """Cliente de alto nivel para a API Mailcow REST."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        settings = get_settings()
        self._client = client
        self._base_url = settings.mailcow_api_url.rstrip("/")
        self._apikey = settings.mailcow_api_key

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {"X-API-Key": self._apikey}

    async def _get(self, path: str) -> Any:
        """GET request com retry. Retorna JSON ou levanta IntegrationError."""
        url = f"{self._base_url}/api/v1{path}"
        resp = await request_with_retry(
            self._client, "GET", url, headers=self._headers()
        )
        if resp.status_code >= 400:
            raise IntegrationError(
                f"Mailcow API GET {path} falhou ({resp.status_code}): "
                f"{resp.text[:300]}"
            )
        return resp.json()

    async def _post(self, path: str, data: dict[str, Any]) -> Any:
        """POST request com retry. Retorna JSON ou levanta IntegrationError."""
        url = f"{self._base_url}/api/v1{path}"
        resp = await request_with_retry(
            self._client, "POST", url, json=data, headers=self._headers()
        )
        if resp.status_code >= 400:
            raise IntegrationError(
                f"Mailcow API POST {path} falhou ({resp.status_code}): "
                f"{resp.text[:300]}"
            )
        return resp.json()

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health(self) -> dict[str, Any]:
        """Verifica conectividade com a API Mailcow.

        Faz GET /get/domain/all e retorna metadados basicos.
        Nao destrutivo — seguro para health checks.
        """
        domains = await self._get("/get/domain/all")
        count = len(domains) if isinstance(domains, list) else 0
        log.info("mailcow.health", domains=count)
        return {"status": "ok", "domains": count}

    async def status(self) -> dict[str, Any]:
        """Status agregado: dominios, contagem de mailboxes, fila.

        Composta de multiplas chamadas GET — use para dashboards,
        nao para health checks de baixa latencia.
        """
        domains = await self._get("/get/domain/all")
        domain_list = domains if isinstance(domains, list) else []
        total_mailboxes = 0
        for d in domain_list:
            domain_name = d.get("domain_name", "")
            if domain_name:
                try:
                    mboxes = await self._get(f"/get/mailbox/{domain_name}")
                    if isinstance(mboxes, list):
                        total_mailboxes += len(mboxes)
                except IntegrationError:
                    pass  # log e continua

        queue_info: dict[str, Any] = {}
        try:
            queue_info = await self._get("/get/postfix/queue/all")
        except IntegrationError:
            queue_info = {"error": "unavailable"}

        result = {
            "status": "ok",
            "domains": len(domain_list),
            "mailboxes": total_mailboxes,
            "queue": queue_info,
        }
        log.info(
            "mailcow.status",
            domains=result["domains"],
            mailboxes=result["mailboxes"],
        )
        return result

    # ------------------------------------------------------------------
    # Dominios
    # ------------------------------------------------------------------

    async def list_domains(self) -> list[dict[str, Any]]:
        """Lista todos os dominios configurados no Mailcow."""
        result = await self._get("/get/domain/all")
        domains = result if isinstance(result, list) else []
        log.info("mailcow.list_domains", count=len(domains))
        return domains

    async def get_domain(self, domain: str) -> dict[str, Any]:
        """Obtem detalhes de um dominio especifico."""
        result = await self._get(f"/get/domain/{domain}")
        log.info("mailcow.get_domain", domain=domain)
        return result

    async def create_domain(
        self,
        domain: str,
        description: str = "",
        aliases: int = 0,
        mailboxes: int = 0,
        mailbox_quota: int = 0,
        quota: int = 0,
        active: bool = True,
    ) -> Any:
        """Cria um novo dominio no Mailcow.

        Args:
            domain: Nome do dominio (ex: "v7m.org").
            description: Descricao do dominio.
            aliases: Limite de aliases (-1 = ilimitado).
            mailboxes: Limite de mailboxes (-1 = ilimitado).
            mailbox_quota: Quota por mailbox em MB (0 = ilimitado).
            quota: Quota total do dominio em MB (0 = ilimitado).
            active: Se o dominio deve estar ativo.
        """
        payload: dict[str, Any] = {
            "domain": domain,
            "description": description,
            "aliases": str(aliases),
            "mailboxes": str(mailboxes),
            "mailbox_quota": str(mailbox_quota),
            "quota": str(quota),
            "active": int(active),
        }
        result = await self._post("/add/domain", payload)
        log.info("mailcow.create_domain", domain=domain)
        return result

    async def edit_domain(
        self,
        domain: str,
        *,
        description: str | None = None,
        active: bool | None = None,
        aliases: int | None = None,
        mailboxes: int | None = None,
        quota: int | None = None,
    ) -> Any:
        """Edita um dominio existente. Apenas campos nao-None sao enviados."""
        payload: dict[str, Any] = {"items": [domain]}
        if description is not None:
            payload["attr"] = payload.get("attr", {})
            payload["attr"]["description"] = description
        if active is not None:
            payload["attr"] = payload.get("attr", {})
            payload["attr"]["active"] = int(active)
        if aliases is not None:
            payload["attr"] = payload.get("attr", {})
            payload["attr"]["aliases"] = str(aliases)
        if mailboxes is not None:
            payload["attr"] = payload.get("attr", {})
            payload["attr"]["mailboxes"] = str(mailboxes)
        if quota is not None:
            payload["attr"] = payload.get("attr", {})
            payload["attr"]["quota"] = str(quota)
        result = await self._post("/edit/domain", payload)
        log.info("mailcow.edit_domain", domain=domain)
        return result

    async def delete_domain(self, domain: str, *, confirm: bool = False) -> Any:
        """Remove um dominio. OPERACAO DESTRUTIVA — exige confirm=True."""
        if not confirm:
            raise ValueError(_CONFIRM_REQUIRED)
        result = await self._post("/delete/domain", {"items": [domain]})
        log.warning("mailcow.delete_domain", domain=domain)
        return result

    # ------------------------------------------------------------------
    # Mailboxes
    # ------------------------------------------------------------------

    async def list_mailboxes(self, domain: str) -> list[dict[str, Any]]:
        """Lista todas as mailboxes de um dominio."""
        result = await self._get(f"/get/mailbox/{domain}")
        mailboxes = result if isinstance(result, list) else []
        log.info("mailcow.list_mailboxes", domain=domain, count=len(mailboxes))
        return mailboxes

    async def get_mailbox(self, addr: str) -> dict[str, Any]:
        """Obtem detalhes de uma mailbox especifica (ex: user@v7m.org)."""
        result = await self._get(f"/get/mailbox/{addr}")
        log.info("mailcow.get_mailbox", addr=addr)
        return result

    async def create_mailbox(
        self,
        local_part: str,
        domain: str,
        password: str,
        *,
        name: str = "",
        quota: int = 1024,
        active: bool = True,
        force_pw_update: bool = False,
        tls_enforce_in: bool = True,
        tls_enforce_out: bool = True,
    ) -> Any:
        """Cria uma nova mailbox.

        Args:
            local_part: Parte local do email (antes do @).
            domain: Dominio (ex: "v7m.org").
            password: Senha da mailbox.
            name: Nome de exibicao.
            quota: Quota em MB (0 = usa default do dominio).
            active: Se a mailbox deve estar ativa.
            force_pw_update: Forca troca de senha no primeiro login.
            tls_enforce_in: Forca TLS para emails recebidos.
            tls_enforce_out: Forca TLS para emails enviados.
        """
        payload: dict[str, Any] = {
            "local_part": local_part,
            "domain": domain,
            "password": password,
            "password2": password,
            "name": name,
            "quota": str(quota),
            "active": int(active),
            "force_pw_update": int(force_pw_update),
            "tls_enforce_in": int(tls_enforce_in),
            "tls_enforce_out": int(tls_enforce_out),
        }
        result = await self._post("/add/mailbox", payload)
        log.info(
            "mailcow.create_mailbox",
            addr=f"{local_part}@{domain}",
            quota=quota,
        )
        return result

    async def edit_mailbox(
        self,
        addr: str,
        *,
        name: str | None = None,
        quota: int | None = None,
        active: bool | None = None,
        password: str | None = None,
        tls_enforce_in: bool | None = None,
        tls_enforce_out: bool | None = None,
    ) -> Any:
        """Edita uma mailbox existente. Apenas campos nao-None sao enviados."""
        payload: dict[str, Any] = {"items": [addr]}
        attr: dict[str, Any] = {}
        if name is not None:
            attr["name"] = name
        if quota is not None:
            attr["quota"] = str(quota)
        if active is not None:
            attr["active"] = int(active)
        if password is not None:
            attr["password"] = password
        if tls_enforce_in is not None:
            attr["tls_enforce_in"] = int(tls_enforce_in)
        if tls_enforce_out is not None:
            attr["tls_enforce_out"] = int(tls_enforce_out)
        if attr:
            payload["attr"] = attr
        result = await self._post("/edit/mailbox", payload)
        log.info("mailcow.edit_mailbox", addr=addr, fields=list(attr.keys()))
        return result

    async def delete_mailbox(
        self, addr: str, *, confirm: bool = False
    ) -> Any:
        """Remove uma mailbox. OPERACAO DESTRUTIVA — exige confirm=True."""
        if not confirm:
            raise ValueError(_CONFIRM_REQUIRED)
        result = await self._post("/delete/mailbox", {"items": [addr]})
        log.warning("mailcow.delete_mailbox", addr=addr)
        return result

    # ------------------------------------------------------------------
    # Aliases
    # ------------------------------------------------------------------

    async def list_aliases(self) -> list[dict[str, Any]]:
        """Lista todos os aliases configurados."""
        result = await self._get("/get/alias/all")
        aliases = result if isinstance(result, list) else []
        log.info("mailcow.list_aliases", count=len(aliases))
        return aliases

    async def create_alias(
        self,
        address: str,
        goto: str | list[str],
        *,
        active: bool = True,
    ) -> Any:
        """Cria um alias de email.

        Args:
            address: Endereco do alias (ex: "info@v7m.org").
            goto: Destino(s) — string unica ou lista de enderecos.
            active: Se o alias deve estar ativo.
        """
        goto_str = goto if isinstance(goto, str) else ",".join(goto)
        payload: dict[str, Any] = {
            "address": address,
            "goto": goto_str,
            "active": int(active),
        }
        result = await self._post("/add/alias", payload)
        log.info("mailcow.create_alias", address=address, goto=goto_str)
        return result

    async def delete_alias(
        self, alias_id: int | str, *, confirm: bool = False
    ) -> Any:
        """Remove um alias. OPERACAO DESTRUTIVA — exige confirm=True."""
        if not confirm:
            raise ValueError(_CONFIRM_REQUIRED)
        result = await self._post("/delete/alias", {"items": [str(alias_id)]})
        log.warning("mailcow.delete_alias", alias_id=alias_id)
        return result

    # ------------------------------------------------------------------
    # DKIM
    # ------------------------------------------------------------------

    async def get_dkim(self, domain: str) -> dict[str, Any]:
        """Obtem chaves DKIM de um dominio."""
        result = await self._get(f"/get/dkim/{domain}")
        log.info("mailcow.get_dkim", domain=domain)
        return result

    async def generate_dkim(
        self,
        domain: str,
        *,
        key_size: int = 2048,
        selector: str = "dkim",
    ) -> Any:
        """Gera novas chaves DKIM para um dominio.

        Args:
            domain: Dominio alvo.
            key_size: Tamanho da chave RSA (1024, 2048, 4096).
            selector: Selector DKIM (default: "dkim").
        """
        payload: dict[str, Any] = {
            "key_size": str(key_size),
            "selector": selector,
        }
        result = await self._post(f"/add/dkim/{domain}", payload)
        log.info(
            "mailcow.generate_dkim",
            domain=domain,
            key_size=key_size,
            selector=selector,
        )
        return result

    # ------------------------------------------------------------------
    # Fila Postfix
    # ------------------------------------------------------------------

    async def get_queue(self) -> Any:
        """Obtem status da fila de email Postfix."""
        result = await self._get("/get/postfix/queue/all")
        log.info("mailcow.get_queue")
        return result

    async def flush_queue(self) -> Any:
        """Forca envio imediato de todos os emails na fila."""
        result = await self._post("/edit/postfix/queue/flush", {})
        log.info("mailcow.flush_queue")
        return result

    async def delete_queue_item(self, item_id: str, *, confirm: bool = False) -> Any:
        """Remove um item da fila. OPERACAO DESTRUTIVA — exige confirm=True."""
        if not confirm:
            raise ValueError(_CONFIRM_REQUIRED)
        result = await self._post(
            "/delete/postfix/queue/item", {"items": [item_id]}
        )
        log.warning("mailcow.delete_queue_item", item_id=item_id)
        return result

    # ------------------------------------------------------------------
    # Logs
    # ------------------------------------------------------------------

    async def get_logs(
        self,
        *,
        limit: int = 100,
        page: int = 1,
        filter_type: str = "ALL",
    ) -> Any:
        """Obtem logs do Mailcow.

        Args:
            limit: Numero maximo de entradas.
            page: Pagina (1-indexed).
            filter_type: Filtro de tipo ("ALL", "DKIM", "SPAM", etc.).
        """
        params = f"?limit={limit}&page={page}"
        if filter_type != "ALL":
            params += f"&filter_type={filter_type}"
        result = await self._get(f"/get/logs/all{params}")
        log.info("mailcow.get_logs", limit=limit, page=page)
        return result
