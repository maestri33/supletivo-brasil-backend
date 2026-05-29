import hashlib
import hmac
import os

import pytest
from sqlalchemy import select

from app.models import OutboundJob
from app.services import checkout_service

EID = "b2c3d4e5-0000-4000-8000-000000000002"
CUSTOMER = {"name": "Joao", "email": "a@b.com", "phone_number": "11999887766"}

WEBHOOK_PAYLOAD = {
    "order_nsu": EID,
    "transaction_nsu": "a4495b16-c593-4de2-9ff0-83ce89acd0d8",
    "invoice_slug": "VtRJSJkMd",
    "receipt_url": "https://recibo.infinitepay.io/abc",
    "amount": 101,
    "paid_amount": 106,
    "installments": 1,
    "capture_method": "credit_card",
}


async def _create(db, monkeypatch):
    async def fake_create(payload):
        return {"url": "https://x/y"}

    monkeypatch.setattr(checkout_service, "create_checkout_link", fake_create)
    await checkout_service.create_checkout(db, {"external_id": EID, "customer": CUSTOMER})
    await db.commit()


async def test_webhook_pays_and_enqueues_backend(db, monkeypatch):
    await _create(db, monkeypatch)

    async def fake_check(**kw):
        return {"success": True, "paid": True, "installments": 1, "capture_method": "credit_card"}

    monkeypatch.setattr(checkout_service, "payment_check", fake_check)

    res = await checkout_service.handle_infinitepay_webhook(db, EID, WEBHOOK_PAYLOAD)
    await db.commit()
    assert res == {"ok": True, "paid": True}

    got = await checkout_service.get_checkout(db, EID)
    assert got["is_paid"] is True
    assert got["receipt_url"] == "https://recibo.infinitepay.io/abc"

    jobs = (await db.execute(select(OutboundJob).order_by(OutboundJob.created_at))).scalars().all()
    paid_jobs = [j for j in jobs if j.payload.get("paid") is True]
    assert len(paid_jobs) == 1
    assert paid_jobs[0].payload["receipt_url"] == "https://recibo.infinitepay.io/abc"
    assert paid_jobs[0].payload["amount"] == 101
    assert paid_jobs[0].payload["paid_amount"] == 106


async def test_webhook_rejects_order_nsu_mismatch(db, monkeypatch):
    await _create(db, monkeypatch)
    bad = dict(WEBHOOK_PAYLOAD, order_nsu="c3d4e5f6-0000-4000-8000-000000000003")
    with pytest.raises(checkout_service.ValidationError):
        await checkout_service.handle_infinitepay_webhook(db, EID, bad)


async def test_webhook_unverified_payment_raises(db, monkeypatch):
    await _create(db, monkeypatch)

    async def fake_check(**kw):
        return {"success": False}

    monkeypatch.setattr(checkout_service, "payment_check", fake_check)
    with pytest.raises(checkout_service.ValidationError):
        await checkout_service.handle_infinitepay_webhook(db, EID, WEBHOOK_PAYLOAD)


async def test_webhook_idempotent_when_already_paid(db, monkeypatch):
    await _create(db, monkeypatch)

    async def fake_check(**kw):
        return {"success": True, "paid": True}

    monkeypatch.setattr(checkout_service, "payment_check", fake_check)

    r1 = await checkout_service.handle_infinitepay_webhook(db, EID, WEBHOOK_PAYLOAD)
    await db.commit()
    assert r1["paid"] is True

    r2 = await checkout_service.handle_infinitepay_webhook(db, EID, WEBHOOK_PAYLOAD)
    await db.commit()
    assert r2.get("duplicate") is True


# ── COD-30: Webhook security tests ────────────────────────────────────────────


async def test_webhook_hmac_valid_signature_accepted(db, monkeypatch, client):
    """HMAC com assinatura valida deve aceitar o webhook."""
    await _create(db, monkeypatch)

    async def fake_check(**kw):
        return {"success": True, "paid": True, "installments": 1, "capture_method": "credit_card"}

    monkeypatch.setattr(checkout_service, "payment_check", fake_check)

    secret = "test-secret-key-12345"
    monkeypatch.setenv("INFINITEPAY_WEBHOOK_SECRET", secret)

    import json

    body = json.dumps(WEBHOOK_PAYLOAD).encode()
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    from app.utils.crypto import encrypt_external_id

    encrypted = encrypt_external_id(EID)
    r = await client.post(
        f"/api/v1/webhook/?external_id={encrypted}",
        content=body,
        headers={
            "Content-Type": "application/json",
            "x-infinitepay-signature": signature,
        },
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True


async def test_webhook_hmac_invalid_signature_rejected(db, monkeypatch, client):
    """HMAC com assinatura invalida deve rejeitar com 401."""
    await _create(db, monkeypatch)

    async def fake_check(**kw):
        return {"success": True, "paid": True}

    monkeypatch.setattr(checkout_service, "payment_check", fake_check)

    monkeypatch.setenv("INFINITEPAY_WEBHOOK_SECRET", "test-secret-key-12345")

    import json

    body = json.dumps(WEBHOOK_PAYLOAD).encode()
    bad_signature = "a" * 64  # assinatura obviamente invalida

    from app.utils.crypto import encrypt_external_id

    encrypted = encrypt_external_id(EID)
    r = await client.post(
        f"/api/v1/webhook/?external_id={encrypted}",
        content=body,
        headers={
            "Content-Type": "application/json",
            "x-infinitepay-signature": bad_signature,
        },
    )
    assert r.status_code == 401


async def test_webhook_ip_allowlist_allows_configured_ip(db, monkeypatch, client):
    """IP dentro do CIDR permitido deve aceitar o webhook."""
    await _create(db, monkeypatch)

    async def fake_check(**kw):
        return {"success": True, "paid": True, "installments": 1, "capture_method": "credit_card"}

    monkeypatch.setattr(checkout_service, "payment_check", fake_check)

    # Limpa HMAC secret de testes anteriores e configura apenas IP allow-list
    os.environ.pop("INFINITEPAY_WEBHOOK_SECRET", None)
    os.environ["INFINITEPAY_WEBHOOK_ALLOWED_CIDRS"] = "192.168.1.100/32"

    from app.utils.crypto import encrypt_external_id

    encrypted = encrypt_external_id(EID)
    r = await client.post(
        f"/api/v1/webhook/?external_id={encrypted}",
        json=WEBHOOK_PAYLOAD,
        headers={"X-Forwarded-For": "192.168.1.100"},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True


async def test_webhook_ip_allowlist_rejects_unknown_ip(db, monkeypatch, client):
    """IP fora do CIDR permitido deve rejeitar com 403."""
    await _create(db, monkeypatch)

    async def fake_check(**kw):
        return {"success": True, "paid": True}

    monkeypatch.setattr(checkout_service, "payment_check", fake_check)

    # Limpa HMAC secret de testes anteriores — testa apenas IP allow-list
    os.environ.pop("INFINITEPAY_WEBHOOK_SECRET", None)
    os.environ["INFINITEPAY_WEBHOOK_ALLOWED_CIDRS"] = "192.168.1.100/32"

    from app.utils.crypto import encrypt_external_id

    encrypted = encrypt_external_id(EID)
    r = await client.post(
        f"/api/v1/webhook/?external_id={encrypted}",
        json=WEBHOOK_PAYLOAD,
        headers={"X-Forwarded-For": "10.0.0.99"},
    )
    assert r.status_code == 403


async def test_webhook_ip_allowlist_disabled_allows_all(db, monkeypatch, client):
    """CIDRS="" explicitamente desabilita o IP allow-list (dev)."""
    await _create(db, monkeypatch)

    async def fake_check(**kw):
        return {"success": True, "paid": True, "installments": 1, "capture_method": "credit_card"}

    monkeypatch.setattr(checkout_service, "payment_check", fake_check)

    # Limpa HMAC secret de testes anteriores — testa apenas IP allow-list desabilitado
    os.environ.pop("INFINITEPAY_WEBHOOK_SECRET", None)
    monkeypatch.setenv("INFINITEPAY_WEBHOOK_ALLOWED_CIDRS", "")

    from app.utils.crypto import encrypt_external_id

    encrypted = encrypt_external_id(EID)
    r = await client.post(
        f"/api/v1/webhook/?external_id={encrypted}",
        json=WEBHOOK_PAYLOAD,
        headers={"X-Forwarded-For": "10.0.0.99"},  # any IP works
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True


async def test_health_reports_webhook_security_status(client, monkeypatch):
    """Health check deve reportar status da configuracao de seguranca."""
    monkeypatch.setenv("INFINITEPAY_WEBHOOK_SECRET", "configured")
    monkeypatch.setenv("INFINITEPAY_WEBHOOK_ALLOWED_CIDRS", "192.168.1.0/24")

    r = await client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["webhook_security"]["webhook_hmac_configured"] is True
    assert data["webhook_security"]["webhook_ip_allowlist_configured"] is True
    assert data["webhook_security"]["webhook_ip_allowlist_custom"] is True
