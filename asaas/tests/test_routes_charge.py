"""Tests das rotas /api/v1/charge e da bridge webhook -> charge."""

from __future__ import annotations

from sqlalchemy import select

from app.models import Customer, Payment


def _mock_charge(charge_id="pay_remote_1"):
    return {
        "id": charge_id,
        "status": "PENDING",
        "value": 250.0,
        "billingType": "PIX",
        "dueDate": "2030-12-31",
    }


def _mock_qr():
    return {
        "encodedImage": "PNG_BASE64_FAKE",
        "payload": "00020126360014br.gov.bcb.pix...",
    }


async def _seed_customer(db, ext_id="aluno_42", asaas_id="cus_42"):
    row = Customer(
        external_id=ext_id,
        asaas_id=asaas_id,
        name="Maria",
        cpf_cnpj="07426367980",
    )
    db.add(row)
    await db.commit()
    return row


# ───────────────────────── POST /charge/pix ──────────────────────────


async def test_post_charge_pix_falta_customer_400(client, seeded_apikey, fake_asaas):
    """external_id novo sem payer -> 400 customer_required."""
    fake_asaas.find_customer_by_external_reference.return_value = None
    r = await client.post(
        "/api/v1/charge/pix",
        json={"external_id": "aluno_novo", "amount": 100.0},
    )
    assert r.status_code == 400
    assert "customer_required" in r.json()["detail"]


async def test_post_charge_pix_com_customer_existente(db, client, seeded_apikey, fake_asaas):
    await _seed_customer(db)
    fake_asaas.create_payment.return_value = _mock_charge()
    fake_asaas.get_payment_pix_qr_code.return_value = _mock_qr()
    r = await client.post(
        "/api/v1/charge/pix",
        json={
            "external_id": "aluno_42",
            "amount": 250.00,
            "description": "Mensalidade",
            "due_date": "2030-12-31",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "PENDING"
    assert body["amount"] == 250.0
    assert body["external_id"] == "aluno_42"
    assert body["pix"]["payload"].startswith("00020126")
    assert body["pix"]["encoded_image"] == "PNG_BASE64_FAKE"


async def test_post_charge_pix_inline_payer_cria_customer(db, client, seeded_apikey, fake_asaas):
    fake_asaas.find_customer_by_external_reference.return_value = None
    fake_asaas.create_customer.return_value = {
        "id": "cus_brand_new",
        "name": "Maria",
        "cpfCnpj": "07426367980",
    }
    fake_asaas.create_payment.return_value = _mock_charge("pay_R1")
    fake_asaas.get_payment_pix_qr_code.return_value = _mock_qr()
    r = await client.post(
        "/api/v1/charge/pix",
        json={
            "external_id": "aluno_novo",
            "amount": 99.99,
            "payer": {
                "name": "Maria",
                "cpf_cnpj": "074.263.679-80",
                "email": "m@e.com",
            },
        },
    )
    assert r.status_code == 200
    db.expire_all()
    row = (
        await db.execute(select(Customer).where(Customer.external_id == "aluno_novo"))
    ).scalar_one()
    assert row.asaas_id == "cus_brand_new"


async def test_post_charge_pix_amount_zero_422(client, seeded_apikey, fake_asaas):
    # pydantic field constraint gt=0
    r = await client.post(
        "/api/v1/charge/pix",
        json={"external_id": "aluno_42", "amount": 0},
    )
    assert r.status_code == 422


async def test_post_charge_pix_idempotencia(db, client, seeded_apikey, fake_asaas):
    await _seed_customer(db)
    fake_asaas.create_payment.return_value = _mock_charge("pay_R1")
    fake_asaas.get_payment_pix_qr_code.return_value = _mock_qr()
    payload = {
        "external_id": "aluno_42",
        "amount": 10.0,
        "payment_id": "idem_x",
    }
    r1 = await client.post("/api/v1/charge/pix", json=payload)
    assert r1.status_code == 200
    r2 = await client.post("/api/v1/charge/pix", json=payload)
    assert r2.status_code == 400
    assert "payment_id_already_exists" in r2.json()["detail"]


# ───────────────────────── GET /charge/{id} + /status ──────────────────────────


async def test_get_charge_completo(db, client, seeded_apikey, fake_asaas):
    await _seed_customer(db)
    fake_asaas.create_payment.return_value = _mock_charge("pay_R1")
    fake_asaas.get_payment_pix_qr_code.return_value = _mock_qr()
    created = (
        await client.post(
            "/api/v1/charge/pix",
            json={"external_id": "aluno_42", "amount": 10.0},
        )
    ).json()
    pid = created["payment_id"]

    r = await client.get(f"/api/v1/charge/{pid}")
    assert r.status_code == 200
    assert r.json()["payment_id"] == pid
    assert r.json()["pix"]["encoded_image"] == "PNG_BASE64_FAKE"


async def test_get_charge_status_light(db, client, seeded_apikey, fake_asaas):
    await _seed_customer(db)
    fake_asaas.create_payment.return_value = _mock_charge("pay_R1")
    fake_asaas.get_payment_pix_qr_code.return_value = _mock_qr()
    created = (
        await client.post(
            "/api/v1/charge/pix",
            json={"external_id": "aluno_42", "amount": 10.0},
        )
    ).json()
    pid = created["payment_id"]

    r = await client.get(f"/api/v1/charge/{pid}/status")
    assert r.status_code == 200
    body = r.json()
    assert body["payment_id"] == pid
    assert body["status"] == "PENDING"
    # status endpoint nao retorna o pix payload pesado
    assert "pix" not in body


async def test_get_charge_not_found_404(client, seeded_apikey):
    r = await client.get("/api/v1/charge/pay_nao_existe")
    assert r.status_code == 404
    r2 = await client.get("/api/v1/charge/pay_nao_existe/status")
    assert r2.status_code == 404


# ───────────────────────── DELETE /charge/{id} ──────────────────────────


async def test_delete_charge_pending(db, client, seeded_apikey, fake_asaas):
    await _seed_customer(db)
    fake_asaas.create_payment.return_value = _mock_charge("pay_R1")
    fake_asaas.get_payment_pix_qr_code.return_value = _mock_qr()
    created = (
        await client.post(
            "/api/v1/charge/pix",
            json={"external_id": "aluno_42", "amount": 10.0},
        )
    ).json()
    pid = created["payment_id"]

    fake_asaas.delete_payment.return_value = {"deleted": True}
    r = await client.delete(f"/api/v1/charge/{pid}")
    assert r.status_code == 200
    assert r.json()["status"] == "CANCELLED"


async def test_delete_charge_404(client, seeded_apikey):
    r = await client.delete("/api/v1/charge/pay_nao_existe")
    assert r.status_code == 404


# ───────────────────────── webhook bridge ──────────────────────────


async def test_webhook_payment_received_atualiza_charge(
    db, client, seeded_apikey, seeded_token, fake_asaas
):
    await _seed_customer(db)
    fake_asaas.create_payment.return_value = _mock_charge("pay_remote_X")
    fake_asaas.get_payment_pix_qr_code.return_value = _mock_qr()
    created = (
        await client.post(
            "/api/v1/charge/pix",
            json={"external_id": "aluno_42", "amount": 10.0},
        )
    ).json()
    pid = created["payment_id"]

    r = await client.post(
        "/webhook/",
        json={
            "event": "PAYMENT_RECEIVED",
            "payment": {"id": "pay_remote_X", "externalReference": pid},
        },
        headers={"asaas-access-token": seeded_token},
    )
    assert r.status_code == 200

    db.expire_all()
    p = (await db.execute(select(Payment).where(Payment.payment_id == pid))).scalar_one()
    assert p.status == "PAID"


async def test_webhook_payment_overdue_atualiza_charge_expired(
    db, client, seeded_apikey, seeded_token, fake_asaas
):
    await _seed_customer(db)
    fake_asaas.create_payment.return_value = _mock_charge("pay_remote_O")
    fake_asaas.get_payment_pix_qr_code.return_value = _mock_qr()
    created = (
        await client.post(
            "/api/v1/charge/pix",
            json={"external_id": "aluno_42", "amount": 10.0},
        )
    ).json()
    pid = created["payment_id"]

    r = await client.post(
        "/webhook/",
        json={
            "event": "PAYMENT_OVERDUE",
            "payment": {"id": "pay_remote_O", "externalReference": pid},
        },
        headers={"asaas-access-token": seeded_token},
    )
    assert r.status_code == 200

    db.expire_all()
    p = (await db.execute(select(Payment).where(Payment.payment_id == pid))).scalar_one()
    assert p.status == "EXPIRED"


async def test_webhook_transfer_event_nao_afeta_charge(
    db, client, seeded_apikey, seeded_token, fake_asaas
):
    """Evento TRANSFER_DONE nao deve mexer em Payment(kind=charge)."""
    await _seed_customer(db)
    fake_asaas.create_payment.return_value = _mock_charge("pay_remote_Q")
    fake_asaas.get_payment_pix_qr_code.return_value = _mock_qr()
    created = (
        await client.post(
            "/api/v1/charge/pix",
            json={"external_id": "aluno_42", "amount": 10.0},
        )
    ).json()
    pid = created["payment_id"]

    r = await client.post(
        "/webhook/",
        json={
            "event": "TRANSFER_DONE",
            "transfer": {"id": "pay_remote_Q", "status": "DONE"},
        },
        headers={"asaas-access-token": seeded_token},
    )
    assert r.status_code == 200

    db.expire_all()
    p = (await db.execute(select(Payment).where(Payment.payment_id == pid))).scalar_one()
    assert p.status == "PENDING"  # nao mudou
