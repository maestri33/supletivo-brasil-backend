"""Tests do POST /webhook/ e POST /security-validator."""

from __future__ import annotations

from sqlalchemy import func, select

from app.models import Payment, PixKey, WebhookEvent


async def test_webhook_sem_token_401(client):
    r = await client.post("/webhook/", json={"event": "TRANSFER_DONE"})
    assert r.status_code == 401


async def test_webhook_token_errado_401(client, seeded_token):
    r = await client.post(
        "/webhook/", json={"event": "FOO"}, headers={"asaas-access-token": "wrong"}
    )
    assert r.status_code == 401


async def test_webhook_persiste_evento(db, client, seeded_token):
    r = await client.post(
        "/webhook/",
        json={"event": "PAYMENT_RECEIVED", "payment": {"id": "p1"}},
        headers={"asaas-access-token": seeded_token},
    )
    assert r.status_code == 200
    rows = (await db.execute(select(WebhookEvent))).scalars().all()
    assert len(rows) == 1
    assert rows[0].event == "PAYMENT_RECEIVED"


async def test_security_validator_recusa_sem_token(client, seeded_token):
    r = await client.post("/security-validator", json={})
    assert r.status_code == 401


async def test_security_validator_recusa_body_vazio(client, seeded_token):
    """Sem 'type' no payload nao da pra validar — recusa."""
    r = await client.post(
        "/security-validator", json={}, headers={"asaas-access-token": seeded_token}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "REFUSED"
    assert "missing_type" in body["refuseReason"]


async def test_webhook_bridge_atualiza_payment_para_paid(db, client, seeded_token):
    """TRANSFER_DONE com transferId existente vira PAID no nosso DB."""
    db.add(
        PixKey(
            external_id="x",
            key="k",
            key_type="CPF",
            holder_document="11",
            holder_name="t",
            bank_name="b",
        )
    )
    db.add(
        Payment(
            payment_id="pay_test1",
            kind="pixkey",
            pixkey_external_id="x",
            amount=1.0,
            status="SUBMITTED",
            asaas_id="tr_xyz",
        )
    )
    await db.commit()

    r = await client.post(
        "/webhook/",
        json={
            "event": "TRANSFER_DONE",
            "transfer": {"id": "tr_xyz", "status": "DONE"},
        },
        headers={"asaas-access-token": seeded_token},
    )
    assert r.status_code == 200

    db.expire_all()
    p = (await db.execute(select(Payment).where(Payment.payment_id == "pay_test1"))).scalar_one()
    assert p.status == "PAID"


async def test_webhook_bridge_transfer_failed_vira_failed(db, client, seeded_token):
    db.add(
        PixKey(
            external_id="y",
            key="ky",
            key_type="CPF",
            holder_document="11",
            holder_name="t",
            bank_name="b",
        )
    )
    db.add(
        Payment(
            payment_id="pay_test2",
            kind="pixkey",
            pixkey_external_id="y",
            amount=1.0,
            status="SUBMITTED",
            asaas_id="tr_failed",
        )
    )
    await db.commit()

    r = await client.post(
        "/webhook/",
        json={
            "event": "TRANSFER_FAILED",
            "transfer": {"id": "tr_failed", "status": "FAILED"},
        },
        headers={"asaas-access-token": seeded_token},
    )
    assert r.status_code == 200

    db.expire_all()
    p = (await db.execute(select(Payment).where(Payment.payment_id == "pay_test2"))).scalar_one()
    assert p.status == "FAILED"


async def test_webhook_evento_sem_match_nao_quebra(db, client, seeded_token):
    """Evento que nao mapeia pra nenhum Payment nosso ainda persiste e retorna 200."""
    r = await client.post(
        "/webhook/",
        json={
            "event": "TRANSFER_DONE",
            "transfer": {"id": "id_que_nao_existe_aqui", "status": "DONE"},
        },
        headers={"asaas-access-token": seeded_token},
    )
    assert r.status_code == 200
    count = (await db.execute(select(func.count()).select_from(WebhookEvent))).scalar_one()
    assert count == 1
