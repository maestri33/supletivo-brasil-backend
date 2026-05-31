"""Cliente HTTP para o payout Pix via servico interno `asaas`.

CONVENTION §12: o asaas e o UNICO provedor de payout autorizado. Este cliente fala
com o SERVICO interno asaas (nao com a API publica do Asaas).

O asaas detem a fila pesada do dinheiro saindo: enfileira a transferencia, espera
saldo (status AWAITING_BALANCE), retenta e confirma. Aqui so:
  - POST /api/v1/payment           cria o pagamento Pix por pixkey (idempotente por payment_id)
  - GET  /api/v1/payment/{payment_id}  consulta o estado atual

Idempotencia: enviamos `payment_id = Payout.external_reference`. Se o asaas ja conhece
esse payment_id, responde 400 `payment_id_already_exists` — tratamos como "ja existe"
e consultamos o estado, NUNCA duplicamos o pagamento.
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import httpx

from app.config import get_settings
from app.integrations import BaseClient, request_with_retry


@dataclass
class PayoutResult:
    """Estado de um payout no asaas apos criar ou consultar.

    `asaas_status` e o status verbatim do asaas (SCHEDULED/QUEUED/SUBMITTING/SUBMITTED/
    PAID/FAILED/CANCELLED/AWAITING_BALANCE). `error` so vem preenchido em falha
    PERMANENTE (4xx de negocio, ex: pixkey_not_found). Falha transitoria (5xx/timeout)
    NAO retorna aqui — levanta IntegrationError pro worker retentar.
    """

    payment_id: str
    asaas_status: str | None = None
    asaas_id: str | None = None
    error: str | None = None
    already_existed: bool = False

    @property
    def is_permanent_error(self) -> bool:
        return self.error is not None


def _make_default_client() -> httpx.AsyncClient:
    settings = get_settings()
    return httpx.AsyncClient(
        base_url=settings.asaas_base_url,
        timeout=settings.http_timeout,
    )


def _detail(resp: httpx.Response) -> str | None:
    """Extrai o codigo de erro de negocio do corpo {"detail": "..."} do asaas."""
    try:
        body = resp.json()
    except Exception:  # noqa: BLE001 — corpo nao-JSON
        return None
    if isinstance(body, dict):
        d = body.get("detail")
        return d if isinstance(d, str) else None
    return None


class AsaasPayoutClient(BaseClient):
    """Cliente do servico interno asaas para payout Pix por pixkey."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        super().__init__(client or _make_default_client())

    async def create_payout(
        self,
        *,
        external_id: str | UUID,
        amount_cents: int,
        payment_id: str,
        description: str | None = None,
    ) -> PayoutResult:
        """Cria um pagamento Pix imediato para a pixkey do beneficiario.

        `external_id` = external_id da pixkey cadastrada no asaas (no nosso sistema,
        o proprio UUID do usuario). `payment_id` = external_reference (idempotencia).
        `amount_cents` e convertido pra BRL (o asaas recebe reais).

        Levanta IntegrationError em falha transitoria (worker deve retentar).
        Retorna PayoutResult.error preenchido em falha permanente.
        """
        body = {
            "external_id": str(external_id),
            "amount": round(amount_cents / 100, 2),
            "payment_id": payment_id,
            "description": description,
        }
        try:
            resp = await request_with_retry(
                self.client, "POST", "/api/v1/payment", json=body
            )
        except httpx.HTTPStatusError as exc:
            detail = _detail(exc.response)
            if detail == "payment_id_already_exists":
                # Idempotente: ja existe no asaas. Consulta o estado atual.
                self.log.info("payout_already_exists", payment_id=payment_id)
                return await self.get_payout(payment_id, _existed=True)
            # Demais 4xx = falha permanente de negocio (pixkey_not_found, invalid_amount...)
            self.log.error(
                "payout_rejected", payment_id=payment_id,
                status=exc.response.status_code, detail=detail,
            )
            return PayoutResult(
                payment_id=payment_id,
                error=detail or f"http_{exc.response.status_code}",
            )

        data = resp.json()
        self.log.info(
            "payout_created",
            payment_id=data.get("payment_id", payment_id),
            asaas_status=data.get("status"),
            asaas_id=data.get("asaas_id"),
        )
        return PayoutResult(
            payment_id=data.get("payment_id", payment_id),
            asaas_status=data.get("status"),
            asaas_id=data.get("asaas_id"),
        )

    async def get_payout(self, payment_id: str, *, _existed: bool = False) -> PayoutResult:
        """Consulta o estado de um pagamento no asaas por payment_id.

        Levanta IntegrationError em falha transitoria. Retorna error='not_found'
        se o asaas nao conhece o payment_id.
        """
        try:
            resp = await request_with_retry(
                self.client, "GET", f"/api/v1/payment/{payment_id}"
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return PayoutResult(payment_id=payment_id, error="not_found", already_existed=_existed)
            return PayoutResult(
                payment_id=payment_id,
                error=_detail(exc.response) or f"http_{exc.response.status_code}",
                already_existed=_existed,
            )

        data = resp.json()
        return PayoutResult(
            payment_id=data.get("payment_id", payment_id),
            asaas_status=data.get("status"),
            asaas_id=data.get("asaas_id"),
            already_existed=_existed,
        )

    async def aclose(self) -> None:
        await self.client.aclose()
