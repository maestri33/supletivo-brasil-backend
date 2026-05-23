from pydantic import BaseModel

from app.integrations import BaseClient, request_with_retry


class CustomerIn(BaseModel):
    name: str
    email: str
    phone_number: str


class CheckoutCreate(BaseModel):
    external_id: str
    customer: CustomerIn


class CheckoutOut(BaseModel):
    external_id: str
    is_paid: bool = False
    checkout_url: str | None = None
    receipt_url: str | None = None
    invoice_slug: str | None = None
    transaction_nsu: str | None = None
    capture_method: str | None = None
    installments: int | None = None
    created_at: str | None = None
    updated_at: str | None = None


class InfinitePayClient(BaseClient):
    """POST /api/v1/checkout/ — criar link de pagamento
    GET  /api/v1/checkout/{external_id}/ — consultar checkout"""

    async def create_checkout(self, payload: CheckoutCreate) -> CheckoutOut:
        resp = await request_with_retry(
            self.client, "POST", "/api/v1/checkout/", json=payload.model_dump()
        )
        return CheckoutOut(**resp.json())

    async def get_checkout(self, external_id: str) -> CheckoutOut:
        resp = await request_with_retry(
            self.client, "GET", f"/api/v1/checkout/{external_id}/"
        )
        return CheckoutOut(**resp.json())
