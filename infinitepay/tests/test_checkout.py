import pytest
from sqlalchemy import select

from app.integrations.infinitepay_client import InfinitePayError
from app.models.models import Checkout, OutboundJob
from app.services import checkout_service

EID = "a1b2c3d4-0000-4000-8000-000000000001"
CUSTOMER = {"name": "Joao", "email": "a@b.com", "phone_number": "11999887766"}


async def test_create_checkout_uses_env_defaults_and_enqueues(db, monkeypatch):
    captured: dict = {}

    async def fake_create(payload):
        captured["payload"] = payload
        return {"url": "https://checkout.ipay/abc"}

    monkeypatch.setattr(checkout_service, "create_checkout_link", fake_create)

    out = await checkout_service.create_checkout(db, {"external_id": EID, "customer": CUSTOMER})
    await db.commit()

    assert out == {"external_id": EID, "checkout_url": "https://checkout.ipay/abc"}
    p = captured["payload"]
    assert p["handle"] == "v7m"
    assert p["items"] == [{"quantity": 1, "price": 100, "description": "Padrao"}]
    assert p["order_nsu"] == EID
    assert p["webhook_url"].startswith("https://example.com/api/v1/webhook/?external_id=")

    rows = (await db.execute(select(Checkout))).scalars().all()
    assert len(rows) == 1
    assert str(rows[0].external_id) == EID
    assert rows[0].is_paid is False

    jobs = (await db.execute(select(OutboundJob))).scalars().all()
    assert len(jobs) == 1
    assert jobs[0].payload["paid"] is False
    assert jobs[0].url == "https://example.com/api"


async def test_create_checkout_duplicate_external_id(db, monkeypatch):
    async def fake_create(payload):
        return {"url": "https://x/y"}

    monkeypatch.setattr(checkout_service, "create_checkout_link", fake_create)
    body = {"external_id": EID, "customer": CUSTOMER}

    await checkout_service.create_checkout(db, body)
    await db.commit()

    with pytest.raises(checkout_service.Conflict) as exc:
        await checkout_service.create_checkout(db, body)
    assert exc.value.code == 409


async def test_create_checkout_integration_error(db, monkeypatch):
    async def fake_create(payload):
        raise InfinitePayError("recusado", payload={"success": False}, status_code=400)

    monkeypatch.setattr(checkout_service, "create_checkout_link", fake_create)

    with pytest.raises(checkout_service.IntegrationError) as exc:
        await checkout_service.create_checkout(db, {"external_id": EID, "customer": CUSTOMER})
    assert exc.value.code == 502


async def test_get_returns_checkout_url_when_unpaid(db, monkeypatch):
    async def fake_create(payload):
        return {"url": "https://x/y"}

    monkeypatch.setattr(checkout_service, "create_checkout_link", fake_create)
    await checkout_service.create_checkout(db, {"external_id": EID, "customer": CUSTOMER})
    await db.commit()

    got = await checkout_service.get_checkout(db, EID)
    assert got == {"external_id": EID, "is_paid": False, "checkout_url": "https://x/y"}


async def test_get_unknown_checkout_raises_not_found(db):
    with pytest.raises(checkout_service.NotFound) as exc:
        await checkout_service.get_checkout(db, EID)
    assert exc.value.code == 404
