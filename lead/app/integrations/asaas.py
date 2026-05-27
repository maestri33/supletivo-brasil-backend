"""Cliente Asaas — cobranca PIX (charges).

Espelha o padrao do `InfinitePayClient`: BaseClient + request_with_retry.

Endpoints utilizados (do servico v7m-asaas, NAO da API publica do Asaas):
- POST /api/v1/charge/pix          — cria cobranca PIX, retorna BR Code + QR + asaas_id
- GET  /api/v1/charge/{payment_id} — consulta cobranca completa (com PIX)

O `external_id` enviado e o UUID do lead (mesmo identificador que o asaas
usa para criar/cachear o customer). O `payment_id` retornado e o id interno
do servico asaas (nao o id do Asaas) — usar para correlacao.
"""

from datetime import date

from pydantic import BaseModel, ConfigDict, EmailStr

from app.integrations import BaseClient, request_with_retry


class AsaasPayerIn(BaseModel):
    """Dados do pagador para create_charge_pix.

    Obrigatorio na primeira cobranca para um external_id (cria customer no Asaas).
    Pode ser omitido em chamadas subsequentes para o mesmo external_id.
    """

    name: str
    cpf_cnpj: str
    email: EmailStr | None = None
    mobile_phone: str | None = None


class AsaasChargeCreate(BaseModel):
    external_id: str
    amount: float  # reais (NAO centavos)
    description: str | None = None
    due_date: str | None = None  # YYYY-MM-DD; default = hoje + ASAAS_APP_CHARGE_DEFAULT_DUE_DAYS
    payment_id: str | None = None  # se omitido, asaas gera 'pay_<hex16>'
    payer: AsaasPayerIn | None = None


class AsaasPixOut(BaseModel):
    payload: str  # BR Code copia-e-cola
    encoded_image: str  # PNG base64
    expiration_date: str | None = None


class AsaasChargeOut(BaseModel):
    """Resposta de POST /api/v1/charge/pix e GET /api/v1/charge/{payment_id}."""

    model_config = ConfigDict(extra="ignore")

    payment_id: str
    external_id: str | None = None
    amount: float
    description: str | None = None
    due_date: date | None = None
    status: str  # PENDING | PAID | EXPIRED | CANCELLED | REFUNDED
    asaas_id: str | None = None
    pix: AsaasPixOut | None = None
    last_error: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class AsaasClient(BaseClient):
    """POST /api/v1/charge/pix — cria cobranca PIX
    GET  /api/v1/charge/{payment_id} — consulta cobranca completa"""

    async def create_charge_pix(self, payload: AsaasChargeCreate) -> AsaasChargeOut:
        body = payload.model_dump(exclude_none=True)
        resp = await request_with_retry(self.client, "POST", "/api/v1/charge/pix", json=body)
        return AsaasChargeOut(**resp.json())

    async def get_charge(self, payment_id: str) -> AsaasChargeOut:
        resp = await request_with_retry(self.client, "GET", f"/api/v1/charge/{payment_id}")
        return AsaasChargeOut(**resp.json())
