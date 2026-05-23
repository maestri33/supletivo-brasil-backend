"""Thin, isolated HTTP layer over Asaas API.

Rules:
 - ASAAS_BASE_URL vem de Settings (env): https://api.asaas.com (prod) ou
   https://api-sandbox.asaas.com (sandbox). O cliente prefixa /v3/ em cada path.
 - No business logic here. Every function maps 1:1 to an Asaas endpoint.
 - Raises AsaasError on any non-2xx (caller decides how to handle).
"""

from __future__ import annotations

from typing import Any

import httpx

from ..config import get_settings

_settings = get_settings()
ASAAS_BASE_URL = _settings.asaas_base_url


class AsaasError(Exception):
    def __init__(self, status_code: int, body: Any, message: str = ""):
        self.status_code = status_code
        self.body = body
        super().__init__(message or f"Asaas HTTP {status_code}: {body!r}")


class AsaasClient:
    def __init__(self, api_key: str, *, timeout: float = 30.0):
        if not api_key:
            raise ValueError("api_key is required")
        self._client = httpx.Client(
            base_url=ASAAS_BASE_URL,
            headers={
                "access_token": api_key,
                "User-Agent": "asaas-app/1.0",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

    # ---------- low-level ----------
    def _request(self, method: str, path: str, *, json: Any = None, params: Any = None) -> Any:
        r = self._client.request(method, path, json=json, params=params)
        if r.status_code == 204 or not r.content:
            data: Any = None
        else:
            try:
                data = r.json()
            except ValueError:
                data = r.text
        if r.status_code >= 400:
            raise AsaasError(r.status_code, data)
        return data

    # ---------- account ----------
    def get_my_account(self) -> dict:
        # /v3/myAccount returns the authenticated wallet's profile
        return self._request("GET", "/v3/myAccount")

    def get_balance(self) -> dict:
        return self._request("GET", "/v3/finance/balance")

    # ---------- webhooks ----------
    def list_webhooks(self) -> dict:
        return self._request("GET", "/v3/webhooks")

    def create_webhook(self, payload: dict) -> dict:
        return self._request("POST", "/v3/webhooks", json=payload)

    def delete_webhook(self, webhook_id: str) -> Any:
        return self._request("DELETE", f"/v3/webhooks/{webhook_id}")

    # ---------- transfers (PIX out) ----------
    def create_transfer(self, payload: dict) -> dict:
        return self._request("POST", "/v3/transfers", json=payload)

    def cancel_transfer(self, transfer_id: str) -> Any:
        return self._request("POST", f"/v3/transfers/{transfer_id}/cancel")

    def get_transfer(self, transfer_id: str) -> dict:
        return self._request("GET", f"/v3/transfers/{transfer_id}")

    def list_transfers(self, params: dict | None = None) -> dict:
        return self._request("GET", "/v3/transfers", params=params)

    # ---------- PIX QR Code outbound (copia-e-cola, paying) ----------
    def pay_qr_code(self, payload: str, value: float, description: str | None = None) -> dict:
        body: dict = {
            "qrCode": {"payload": payload},
            "value": round(float(value), 2),
        }
        if description:
            body["description"] = description
        return self._request("POST", "/v3/pix/qrCodes/pay", json=body)

    # ---------- PIX transactions (outbound) ----------
    def get_pix_transaction(self, transaction_id: str) -> dict:
        return self._request("GET", f"/v3/pix/transactions/{transaction_id}")

    def cancel_pix_transaction(self, transaction_id: str) -> Any:
        return self._request("POST", f"/v3/pix/transactions/{transaction_id}/cancel")

    # ---------- customers ----------
    def create_customer(self, payload: dict) -> dict:
        return self._request("POST", "/v3/customers", json=payload)

    def get_customer(self, customer_id: str) -> dict:
        return self._request("GET", f"/v3/customers/{customer_id}")

    def list_customers(self, params: dict | None = None) -> dict:
        return self._request("GET", "/v3/customers", params=params)

    def find_customer_by_external_reference(self, external_reference: str) -> dict | None:
        res = self.list_customers({"externalReference": external_reference, "limit": 1})
        data = res.get("data") or []
        return data[0] if data else None

    def update_customer(self, customer_id: str, payload: dict) -> dict:
        return self._request("POST", f"/v3/customers/{customer_id}", json=payload)

    # ---------- payments (inbound charges) ----------
    def create_payment(self, payload: dict) -> dict:
        return self._request("POST", "/v3/payments", json=payload)

    def get_payment(self, payment_id: str) -> dict:
        return self._request("GET", f"/v3/payments/{payment_id}")

    def list_payments(self, params: dict | None = None) -> dict:
        return self._request("GET", "/v3/payments", params=params)

    def delete_payment(self, payment_id: str) -> Any:
        return self._request("DELETE", f"/v3/payments/{payment_id}")

    def refund_payment(self, payment_id: str, payload: dict | None = None) -> dict:
        return self._request("POST", f"/v3/payments/{payment_id}/refund", json=payload or {})

    def get_payment_pix_qr_code(self, payment_id: str) -> dict:
        """BR Code (copia-e-cola) + base64 PNG da cobranca PIX."""
        return self._request("GET", f"/v3/payments/{payment_id}/pixQrCode")
