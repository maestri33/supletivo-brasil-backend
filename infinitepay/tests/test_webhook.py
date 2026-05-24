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
