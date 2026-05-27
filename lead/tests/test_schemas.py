"""Testes de schemas Pydantic — validação de entrada dos endpoints."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.api.demilitarized.checkouts import CheckoutPatch, CheckoutOut
from app.api.demilitarized.leads import LeadOut, LeadPatch
from app.api.public.auth import (
    CheckRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
)


# ── CheckRequest ─────────────────────────────────────────────────────────────

class TestCheckRequest:
    def test_valid_cpf(self):
        r = CheckRequest(cpf="12345678901")
        assert r.cpf == "12345678901"
        assert r.phone is None
        assert r.external_id is None

    def test_valid_phone(self):
        r = CheckRequest(phone="11999999999")
        assert r.phone == "11999999999"

    def test_valid_external_id(self):
        eid = uuid4()
        r = CheckRequest(external_id=eid)
        assert r.external_id == eid

    def test_all_fields_none_is_valid(self):
        """CheckRequest permite todos os campos None (validação no endpoint)."""
        r = CheckRequest()
        assert r.cpf is None
        assert r.phone is None
        assert r.external_id is None


# ── RegisterRequest ──────────────────────────────────────────────────────────

class TestRegisterRequest:
    def test_valid_fields(self):
        r = RegisterRequest(phone="11999999999", cpf="12345678901")
        assert r.phone == "11999999999"
        assert r.cpf == "12345678901"
        assert r.ref is None

    def test_with_reference(self):
        ref = uuid4()
        r = RegisterRequest(phone="11999999999", cpf="12345678901", ref=ref)
        assert r.ref == ref

    def test_phone_required(self):
        with pytest.raises(ValidationError):
            RegisterRequest(cpf="12345678901")

    def test_cpf_required(self):
        with pytest.raises(ValidationError):
            RegisterRequest(phone="11999999999")


# ── LoginRequest ─────────────────────────────────────────────────────────────

class TestLoginRequest:
    def test_valid(self):
        eid = uuid4()
        r = LoginRequest(external_id=eid, otp="123456")
        assert r.external_id == eid
        assert r.otp == "123456"

    def test_otp_too_short(self):
        with pytest.raises(ValidationError):
            LoginRequest(external_id=uuid4(), otp="123")

    def test_otp_too_long(self):
        with pytest.raises(ValidationError):
            LoginRequest(external_id=uuid4(), otp="1" * 11)


# ── RefreshRequest ───────────────────────────────────────────────────────────

class TestRefreshRequest:
    def test_valid(self):
        r = RefreshRequest(refresh_token="rt_valido")
        assert r.refresh_token == "rt_valido"


# ── LeadPatch ────────────────────────────────────────────────────────────────

class TestLeadPatch:
    def test_valid_status(self):
        r = LeadPatch(status="captured")
        assert r.status == "captured"

    def test_valid_promoter(self):
        pid = uuid4()
        r = LeadPatch(promoter_external_id=pid)
        assert r.promoter_external_id == pid

    def test_both_fields(self):
        pid = uuid4()
        r = LeadPatch(status="waiting", promoter_external_id=pid)
        assert r.status == "waiting"
        assert r.promoter_external_id == pid

    def test_invalid_status(self):
        with pytest.raises(ValidationError):
            LeadPatch(status="invalid_status")

    def test_all_none(self):
        r = LeadPatch()
        assert r.status is None
        assert r.promoter_external_id is None

    def test_enum_coercion(self):
        """Pydantic v2 coerce strings to Enum via model_validate."""
        from app.models import LeadStatus
        r = LeadPatch.model_validate({"status": "captured"})
        assert r.status == LeadStatus.CAPTURED


# ── LeadOut ──────────────────────────────────────────────────────────────────

class TestLeadOut:
    def test_minimal(self):
        r = LeadOut(id=1, external_id=uuid4(), status="captured")
        assert r.status == "captured"
        assert r.promoter_external_id is None

    def test_full(self):
        pid = uuid4()
        eid = uuid4()
        r = LeadOut(
            id=1,
            external_id=eid,
            status="completed",
            promoter_external_id=pid,
            created_at="2026-01-01T00:00:00",
            updated_at="2026-01-02T00:00:00",
        )
        assert r.status == "completed"
        assert r.promoter_external_id == pid


# ── CheckoutPatch ────────────────────────────────────────────────────────────

class TestCheckoutPatch:
    def test_valid_is_paid(self):
        r = CheckoutPatch(is_paid=True)
        assert r.is_paid is True

    def test_valid_checkout_url(self):
        r = CheckoutPatch(checkout_url="https://example.com/checkout")
        assert r.checkout_url == "https://example.com/checkout"

    def test_multiple_fields(self):
        r = CheckoutPatch(
            checkout_url="https://checkout.com/abc",
            receipt_url="https://receipt.com/abc",
            is_paid=True,
            capture_method="ecommerce",
            installments=6,
        )
        assert r.installments == 6
        assert r.capture_method == "ecommerce"
        assert r.is_paid is True

    def test_all_none(self):
        r = CheckoutPatch()
        assert r.is_paid is None
        assert r.checkout_url is None
