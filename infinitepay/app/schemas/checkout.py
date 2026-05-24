from pydantic import BaseModel


class CustomerIn(BaseModel):
    name: str
    email: str
    phone_number: str


class AddressIn(BaseModel):
    cep: str
    street: str
    neighborhood: str
    number: str
    complement: str | None = None


class ItemIn(BaseModel):
    price: int
    description: str
    quantity: int = 1


class CheckoutCreate(BaseModel):
    """Entrada do POST /checkout.

    external_id + customer sao obrigatorios. Os demais campos sao overrides
    opcionais: quando omitidos, usam os defaults do .env (handle, price,
    description, redirect_url).
    """

    external_id: str
    customer: CustomerIn
    address: AddressIn | None = None
    items: list[ItemIn] | None = None
    price: int | None = None
    description: str | None = None
    quantity: int | None = None
    handle: str | None = None
    redirect_url: str | None = None


# ── response schemas ──────────────────────────────────────────────


class CheckoutResponse(BaseModel):
    """Checkout individual — retornado por create, get e list."""

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


class CheckoutListResponse(BaseModel):
    """Wrapper para listagem de checkouts."""

    items: list[CheckoutResponse]
