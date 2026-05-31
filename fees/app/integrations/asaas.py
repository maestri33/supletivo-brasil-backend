"""Cliente do serviço interno `asaas` (dono exclusivo da integração Asaas/PIX).

CONVENTION §12: o fees **não** fala com a API Asaas direto — usa o app `asaas`.
Espelha o padrão de `lead/app/integrations/asaas.py` (BaseClient + retry).

Endpoints usados (do serviço v7m-asaas, não da API pública do Asaas):
- POST /api/v1/payment/qrcode            — paga um BR Code agora (à vista)
- POST /api/v1/payment/qrcode/scheduled  — agenda pagamento de QR estático
- GET  /api/v1/payment/{payment_id}      — consulta status de um pagamento

O `payment_id` é fornecido pelo fees (idempotente) e é a chave de correlação do
webhook de status que o asaas devolve.
"""

from app.integrations import BaseClient, request_with_retry


class AsaasClient(BaseClient):
    async def pay_qrcode(
        self,
        *,
        qrcode_payload: str,
        amount: float,
        payment_id: str,
        description: str | None = None,
    ) -> dict:
        """Paga um BR Code imediatamente (parte à vista)."""
        body: dict = {
            "qrcode_payload": qrcode_payload,
            "amount": amount,
            "payment_id": payment_id,
        }
        if description:
            body["description"] = description
        resp = await request_with_retry(self.client, "POST", "/api/v1/payment/qrcode", json=body)
        return resp.json()

    async def pay_qrcode_scheduled(
        self,
        *,
        qrcode_payload: str,
        amount: float,
        payment_id: str,
        date: str,
        hour: int | None = None,
        minute: int | None = None,
        description: str | None = None,
    ) -> dict:
        """Agenda o pagamento de um BR Code estático (parte agendada)."""
        body: dict = {
            "qrcode_payload": qrcode_payload,
            "amount": amount,
            "payment_id": payment_id,
            "date": date,
        }
        if hour is not None:
            body["hour"] = hour
        if minute is not None:
            body["minute"] = minute
        if description:
            body["description"] = description
        resp = await request_with_retry(
            self.client, "POST", "/api/v1/payment/qrcode/scheduled", json=body
        )
        return resp.json()

    async def get_payment(self, payment_id: str) -> dict:
        resp = await request_with_retry(self.client, "GET", f"/api/v1/payment/{payment_id}")
        return resp.json()
