"""Tests HTTP do /api/v1/payment — fluxo completo com Asaas mockado.

O submit em background roda via BackgroundTasks; com AsyncClient/ASGITransport
elas executam apos a resposta, entao o status pode chegar como QUEUED ou ja
SUBMITTED (o AsaasClient e o stub `fake_asaas`).
"""

from __future__ import annotations

from app.models import PixKey
from tests.test_brcode import STATIC_FIXED, STATIC_VARIABLE


async def _seed(db):
    db.add(
        PixKey(
            external_id="ext1",
            key="key-ext1",
            key_type="CPF",
            holder_document="12345678901",
            holder_name="TESTE",
            bank_name="INTER",
        )
    )
    await db.commit()


def _mock_transfer_ok(fake_asaas, transfer_id="tr_ok"):
    fake_asaas.create_transfer.return_value = {
        "id": transfer_id,
        "status": "PENDING",
    }


async def test_post_payment_pixkey_not_found(client, seeded_apikey):
    r = await client.post("/api/v1/payment", json={"external_id": "no_exist", "amount": 1.0})
    assert r.status_code == 400
    assert r.json()["detail"] == "pixkey_not_found"


async def test_post_payment_invalid_amount_422(client, seeded_apikey):
    """amount<=0 e bloqueado pelo schema (Field gt=0)."""
    r = await client.post("/api/v1/payment", json={"external_id": "x", "amount": -1.0})
    assert r.status_code == 422


async def test_post_payment_imediato(db, client, seeded_apikey, fake_asaas):
    await _seed(db)
    _mock_transfer_ok(fake_asaas)

    r = await client.post(
        "/api/v1/payment",
        json={
            "external_id": "ext1",
            "amount": 0.01,
            "description": "test",
        },
    )
    assert r.status_code == 200
    body = r.json()
    # apos o background task rodar, status pode ter virado SUBMITTED
    assert body["status"] in ("QUEUED", "SUBMITTED")
    assert body["amount"] == 0.01
    assert body["kind"] == "pixkey"


async def test_post_payment_scheduled(db, client, seeded_apikey):
    await _seed(db)
    r = await client.post(
        "/api/v1/payment/scheduled",
        json={
            "external_id": "ext1",
            "amount": 1.0,
            "date": "2030-12-31",
            "hour": 10,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "SCHEDULED"
    assert body["scheduled_for"] is not None


async def test_get_payment_404(client):
    r = await client.get("/api/v1/payment/pay_naoexiste")
    assert r.status_code == 404


async def test_get_payment_lista_vazia(client):
    r = await client.get("/api/v1/payment")
    assert r.status_code == 200
    assert r.json() == []


async def test_payment_qrcode_analyze(client):
    """Endpoint puro, nao mexe em DB nem Asaas."""
    r = await client.post("/api/v1/payment/qrcode/analyze", json={"qrcode_payload": STATIC_FIXED})
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "static"
    assert body["amount"] == 0.01


async def test_payment_qrcode_analyze_payload_curto(client):
    r = await client.post("/api/v1/payment/qrcode/analyze", json={"qrcode_payload": "xx"})
    assert r.status_code == 422  # validacao schema (min_length=20)


async def test_payment_qrcode_imediato_valor_fixo(db, client, seeded_apikey, fake_asaas):
    fake_asaas.pay_qr_code.return_value = {"id": "tr_qr_ok", "status": "PENDING"}
    r = await client.post("/api/v1/payment/qrcode", json={"qrcode_payload": STATIC_FIXED})
    assert r.status_code == 200
    body = r.json()
    assert body["amount"] == 0.01
    assert body["kind"] == "qrcode"


async def test_payment_qrcode_valor_fixo_amount_diferente(client, seeded_apikey):
    r = await client.post(
        "/api/v1/payment/qrcode",
        json={
            "qrcode_payload": STATIC_FIXED,
            "amount": 99.0,
        },
    )
    assert r.status_code == 400
    assert "qrcode_fixed_amount_mismatch" in r.json()["detail"]


async def test_payment_qrcode_variavel_sem_amount(client, seeded_apikey):
    r = await client.post("/api/v1/payment/qrcode", json={"qrcode_payload": STATIC_VARIABLE})
    assert r.status_code == 400
    assert r.json()["detail"] == "qrcode_amount_required"


async def test_payment_cancel_404(client):
    r = await client.post("/api/v1/payment/pay_naoexiste/cancel")
    assert r.status_code == 404


async def test_payment_cancel_scheduled(db, client, seeded_apikey):
    await _seed(db)
    r = await client.post(
        "/api/v1/payment/scheduled",
        json={
            "external_id": "ext1",
            "amount": 1.0,
            "date": "2030-12-31",
            "hour": 10,
        },
    )
    pid = r.json()["payment_id"]

    rc = await client.post(f"/api/v1/payment/{pid}/cancel")
    assert rc.status_code == 200
    assert rc.json()["status"] == "CANCELLED"


async def test_payment_pagination(db, client, seeded_apikey):
    """Confirma que limit/offset funcionam."""
    await _seed(db)
    for _ in range(3):
        await client.post(
            "/api/v1/payment/scheduled",
            json={
                "external_id": "ext1",
                "amount": 1.0,
                "date": "2030-12-31",
                "hour": 10,
            },
        )
    r1 = await client.get("/api/v1/payment?limit=2&offset=0")
    r2 = await client.get("/api/v1/payment?limit=2&offset=2")
    assert len(r1.json()) == 2
    assert len(r2.json()) == 1


async def test_payment_filter_by_kind(db, client, seeded_apikey):
    """Filtra payments por kind=pixkey vs kind=qrcode."""
    await _seed(db)
    # Cria um pixkey payment
    r = await client.post("/api/v1/payment", json={"external_id": "ext1", "amount": 0.01})
    assert r.status_code == 200
    # Lista filtrando por pixkey
    r1 = await client.get("/api/v1/payment?kind=pixkey")
    assert r1.status_code == 200
    assert all(p["kind"] == "pixkey" for p in r1.json())
    # Lista filtrando por qrcode (deve vir vazio)
    r2 = await client.get("/api/v1/payment?kind=qrcode")
    assert r2.status_code == 200
    assert r2.json() == []


async def test_payment_filter_by_kind_invalido(client):
    r = await client.get("/api/v1/payment?kind=invalid")
    assert r.status_code == 400
    assert "invalid_kind" in r.json()["detail"]


async def test_payment_idempotencia_payment_id(db, client, seeded_apikey):
    await _seed(db)
    body = {
        "external_id": "ext1",
        "amount": 1.0,
        "date": "2030-12-31",
        "hour": 10,
        "payment_id": "manual_id_1",
    }
    r1 = await client.post("/api/v1/payment/scheduled", json=body)
    r2 = await client.post("/api/v1/payment/scheduled", json=body)
    assert r1.status_code == 200
    assert r2.status_code == 400
    assert r2.json()["detail"] == "payment_id_already_exists"


async def test_payment_filter_by_status(db, client, seeded_apikey):
    """Filtra payments por status valido."""
    await _seed(db)
    await client.post(
        "/api/v1/payment/scheduled",
        json={"external_id": "ext1", "amount": 1.0, "date": "2030-12-31", "hour": 10},
    )
    r = await client.get("/api/v1/payment?status=SCHEDULED")
    assert r.status_code == 200
    assert len(r.json()) >= 1
    assert all(p["status"] == "SCHEDULED" for p in r.json())


async def test_payment_filter_by_status_invalido(client):
    r = await client.get("/api/v1/payment?status=INVALID_STATUS")
    assert r.status_code == 400
    assert "invalid_status" in r.json()["detail"]


async def test_payment_filter_by_kind_and_status(db, client, seeded_apikey):
    """Combina kind e status no mesmo filtro."""
    await _seed(db)
    await client.post(
        "/api/v1/payment/scheduled",
        json={"external_id": "ext1", "amount": 1.0, "date": "2030-12-31", "hour": 10},
    )
    r = await client.get("/api/v1/payment?kind=pixkey&status=SCHEDULED")
    assert r.status_code == 200
    assert all(p["kind"] == "pixkey" and p["status"] == "SCHEDULED" for p in r.json())


async def test_payment_delete_scheduled(db, client, seeded_apikey):
    """DELETE cancela payment SCHEDULED localmente."""
    await _seed(db)
    r = await client.post(
        "/api/v1/payment/scheduled",
        json={"external_id": "ext1", "amount": 1.0, "date": "2030-12-31", "hour": 10},
    )
    pid = r.json()["payment_id"]
    d = await client.delete(f"/api/v1/payment/{pid}")
    assert d.status_code == 200
    assert d.json()["status"] == "CANCELLED"


async def test_payment_delete_awaiting_balance(db, client, seeded_apikey, fake_asaas):
    """DELETE cancela payment AWAITING_BALANCE localmente."""
    await _seed(db)
    # Para criar AWAITING_BALANCE: injetamos direto no DB
    from datetime import UTC, datetime

    from app.models import Payment as PaymentModel

    row = PaymentModel(
        payment_id="pay_await_1",
        kind="pixkey",
        pixkey_external_id="ext1",
        amount=5.0,
        status="AWAITING_BALANCE",
        updated_at=datetime.now(UTC),
    )
    db.add(row)
    await db.commit()
    d = await client.delete("/api/v1/payment/pay_await_1")
    assert d.status_code == 200
    assert d.json()["status"] == "CANCELLED"


async def test_payment_delete_submitted_fails(db, client, seeded_apikey):
    """DELETE nao permite cancelar status SUBMITTED."""
    from datetime import UTC, datetime

    from app.models import Payment as PaymentModel

    row = PaymentModel(
        payment_id="pay_sub_1",
        kind="pixkey",
        pixkey_external_id="ext1",
        amount=1.0,
        status="SUBMITTED",
        updated_at=datetime.now(UTC),
    )
    db.add(row)
    await db.commit()
    d = await client.delete("/api/v1/payment/pay_sub_1")
    assert d.status_code == 400
    assert "cannot_delete_status" in d.json()["detail"]


async def test_payment_del_404(client):
    d = await client.delete("/api/v1/payment/pay_naoexiste")
    assert d.status_code == 404


async def test_payment_awaiting_balance_sum(db, client, seeded_apikey):
    """Soma valores de payments AWAITING_BALANCE."""
    from datetime import UTC, datetime

    from app.models import Payment as PaymentModel

    for i, amt in enumerate([10.0, 20.50]):
        db.add(
            PaymentModel(
                payment_id=f"pay_ab_sum_{i}",
                kind="pixkey",
                pixkey_external_id="ext1",
                amount=amt,
                status="AWAITING_BALANCE",
                updated_at=datetime.now(UTC),
            )
        )
    await db.commit()
    r = await client.get("/api/v1/payment/awaiting-balance/sum")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "AWAITING_BALANCE"
    assert body["count"] == 2
    assert body["total"] == 30.50
