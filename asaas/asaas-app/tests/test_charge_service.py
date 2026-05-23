"""Tests do app.services.charge — create, status, cancel, webhook."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.integrations.asaas_client import AsaasError
from app.models import Customer, Payment
from app.services import charge as svc
from app.services.customer import PayerData


def _seed_customer(db, ext_id="aluno_42", asaas_id="cus_aluno_42"):
    row = Customer(
        external_id=ext_id,
        asaas_id=asaas_id,
        name="Maria Aluna",
        cpf_cnpj="07426367980",
    )
    db.add(row)
    db.flush()
    return row


def _mock_charge(charge_id="pay_remote_1", asaas_status="PENDING"):
    return {
        "id": charge_id,
        "status": asaas_status,
        "value": 100.0,
        "billingType": "PIX",
        "dueDate": "2030-12-31",
        "externalReference": "pay_test",
    }


def _mock_qr():
    return {
        "encodedImage": "PNG_BASE64_FAKE",
        "payload": "00020126360014br.gov.bcb.pix0114...",
        "expirationDate": "2030-12-31T23:59:59",
    }


# ───────────────────────── create ──────────────────────────


def test_create_invalid_amount(db, seeded_apikey, fake_asaas):
    with pytest.raises(svc.PaymentError, match="invalid_amount"):
        svc.create(
            db,
            external_id="aluno_42",
            amount=0,
            description=None,
            due_date=None,
            payment_id=None,
            payer=None,
        )


def test_create_sem_api_key_falha(db, fake_asaas):
    with pytest.raises(svc.PaymentError, match="asaas_api_key_not_set"):
        svc.create(
            db,
            external_id="aluno_42",
            amount=50.0,
            description="x",
            due_date=None,
            payment_id=None,
            payer=PayerData(name="X", cpf_cnpj="07426367980"),
        )


def test_create_customer_required_quando_external_id_novo_sem_payer(db, seeded_apikey, fake_asaas):
    with pytest.raises(svc.PaymentError, match="customer_required"):
        svc.create(
            db,
            external_id="aluno_novo",
            amount=50.0,
            description="x",
            due_date=None,
            payment_id=None,
            payer=None,
        )


def test_create_due_date_passado_falha(db, seeded_apikey, fake_asaas):
    _seed_customer(db)
    with pytest.raises(svc.PaymentError, match="invalid_due_date"):
        svc.create(
            db,
            external_id="aluno_42",
            amount=50.0,
            description="x",
            due_date="2020-01-01",
            payment_id=None,
            payer=None,
        )


def test_create_due_date_formato_invalido_falha(db, seeded_apikey, fake_asaas):
    _seed_customer(db)
    with pytest.raises(svc.PaymentError, match="invalid_due_date"):
        svc.create(
            db,
            external_id="aluno_42",
            amount=50.0,
            description="x",
            due_date="31/12/2030",  # formato errado
            payment_id=None,
            payer=None,
        )


def test_create_charge_imediato_sem_due_date_usa_default(db, seeded_apikey, fake_asaas):
    _seed_customer(db)
    fake_asaas.create_payment.return_value = _mock_charge("pay_R1")
    fake_asaas.get_payment_pix_qr_code.return_value = _mock_qr()

    row = svc.create(
        db,
        external_id="aluno_42",
        amount=120.50,
        description="Mensalidade",
        due_date=None,
        payment_id=None,
        payer=None,
    )

    assert row.kind == "charge"
    assert row.status == "PENDING"
    assert row.amount == 120.50
    assert row.asaas_id == "pay_R1"
    assert row.qrcode_payload.startswith("00020126")
    assert row.pix_qr_image == "PNG_BASE64_FAKE"
    assert row.due_date is not None
    assert row.due_date >= date.today()
    # confere payload enviado ao Asaas
    call_payload = fake_asaas.create_payment.call_args[0][0]
    assert call_payload["customer"] == "cus_aluno_42"
    assert call_payload["billingType"] == "PIX"
    assert call_payload["value"] == 120.50


def test_create_charge_payment_id_idempotencia(db, seeded_apikey, fake_asaas):
    _seed_customer(db)
    fake_asaas.create_payment.return_value = _mock_charge("pay_R1")
    fake_asaas.get_payment_pix_qr_code.return_value = _mock_qr()
    svc.create(
        db,
        external_id="aluno_42",
        amount=10.0,
        description=None,
        due_date=None,
        payment_id="custom_id_x",
        payer=None,
    )
    db.commit()
    with pytest.raises(svc.PaymentError, match="payment_id_already_exists"):
        svc.create(
            db,
            external_id="aluno_42",
            amount=10.0,
            description=None,
            due_date=None,
            payment_id="custom_id_x",
            payer=None,
        )


def test_create_charge_propaga_falha_asaas(db, seeded_apikey, fake_asaas):
    _seed_customer(db)
    fake_asaas.create_payment.side_effect = AsaasError(400, {"error": "rejected"})
    with pytest.raises(svc.PaymentError, match="asaas_charge_create_failed"):
        svc.create(
            db,
            external_id="aluno_42",
            amount=10.0,
            description=None,
            due_date=None,
            payment_id=None,
            payer=None,
        )


def test_create_charge_qr_fetch_falha_nao_bloqueia(db, seeded_apikey, fake_asaas):
    """Se QR Code falha, criacao prossegue e persiste sem QR."""
    _seed_customer(db)
    fake_asaas.create_payment.return_value = _mock_charge("pay_R2")
    fake_asaas.get_payment_pix_qr_code.side_effect = AsaasError(500, {})
    row = svc.create(
        db,
        external_id="aluno_42",
        amount=10.0,
        description=None,
        due_date=None,
        payment_id=None,
        payer=None,
    )
    assert row.status == "PENDING"
    assert row.asaas_id == "pay_R2"
    assert row.qrcode_payload is None
    assert row.pix_qr_image is None


def test_create_charge_com_payer_inline_cria_customer(db, seeded_apikey, fake_asaas):
    """Sem customer local, payer inline dispara find-or-create."""
    fake_asaas.find_customer_by_external_reference.return_value = None
    fake_asaas.create_customer.return_value = {
        "id": "cus_novo",
        "name": "Maria",
        "cpfCnpj": "07426367980",
        "externalReference": "aluno_novo",
    }
    fake_asaas.create_payment.return_value = _mock_charge("pay_R3")
    fake_asaas.get_payment_pix_qr_code.return_value = _mock_qr()
    row = svc.create(
        db,
        external_id="aluno_novo",
        amount=50.0,
        description="x",
        due_date=None,
        payment_id=None,
        payer=PayerData(name="Maria", cpf_cnpj="074.263.679-80"),
    )
    assert row.status == "PENDING"
    assert row.customer_external_id == "aluno_novo"
    fake_asaas.create_customer.assert_called_once()


# ───────────────────────── webhook ──────────────────────────


def _seed_charge(db, payment_id="pay_chg_1", asaas_id="pay_remote_1", status="PENDING"):
    row = Payment(
        payment_id=payment_id,
        kind="charge",
        customer_external_id="aluno_42",
        amount=100.0,
        status=status,
        asaas_id=asaas_id,
        due_date=date.today() + timedelta(days=3),
    )
    db.add(row)
    db.flush()
    return row


def test_webhook_payment_received_vira_paid(db):
    _seed_customer(db)
    _seed_charge(db, asaas_id="pay_remote_X")
    db.commit()
    updated = svc.apply_webhook(
        db,
        {
            "event": "PAYMENT_RECEIVED",
            "payment": {"id": "pay_remote_X", "externalReference": "pay_chg_1"},
        },
    )
    assert updated is not None
    assert updated.status == "PAID"


def test_webhook_payment_confirmed_vira_paid(db):
    _seed_customer(db)
    _seed_charge(db, asaas_id="pay_remote_Y", payment_id="pay_chg_2")
    db.commit()
    updated = svc.apply_webhook(
        db,
        {
            "event": "PAYMENT_CONFIRMED",
            "payment": {"id": "pay_remote_Y", "externalReference": "pay_chg_2"},
        },
    )
    assert updated.status == "PAID"


def test_webhook_payment_overdue_vira_expired(db):
    _seed_customer(db)
    _seed_charge(db, payment_id="pay_chg_3", asaas_id="pay_Z")
    db.commit()
    updated = svc.apply_webhook(
        db,
        {
            "event": "PAYMENT_OVERDUE",
            "payment": {"id": "pay_Z", "externalReference": "pay_chg_3"},
        },
    )
    assert updated.status == "EXPIRED"


def test_webhook_payment_deleted_vira_cancelled(db):
    _seed_customer(db)
    _seed_charge(db, payment_id="pay_chg_4", asaas_id="pay_D")
    db.commit()
    updated = svc.apply_webhook(
        db,
        {
            "event": "PAYMENT_DELETED",
            "payment": {"id": "pay_D", "externalReference": "pay_chg_4"},
        },
    )
    assert updated.status == "CANCELLED"


def test_webhook_payment_refunded_vira_refunded(db):
    _seed_customer(db)
    _seed_charge(db, payment_id="pay_chg_5", asaas_id="pay_RR", status="PAID")
    db.commit()
    updated = svc.apply_webhook(
        db,
        {
            "event": "PAYMENT_REFUNDED",
            "payment": {"id": "pay_RR", "externalReference": "pay_chg_5"},
        },
    )
    assert updated.status == "REFUNDED"


def test_webhook_event_desconhecido_ignora(db):
    _seed_customer(db)
    _seed_charge(db)
    db.commit()
    assert svc.apply_webhook(db, {"event": "PAYMENT_UNKNOWN_EVENT"}) is None
    assert svc.apply_webhook(db, {"event": "TRANSFER_DONE"}) is None


def test_webhook_event_nao_encontra_payment(db):
    """Webhook chega pra cobranca que nao existe localmente — retorna None."""
    assert (
        svc.apply_webhook(
            db,
            {
                "event": "PAYMENT_RECEIVED",
                "payment": {"id": "asaas_id_que_nao_existe", "externalReference": "x"},
            },
        )
        is None
    )


def test_webhook_event_match_por_asaas_id_quando_external_ref_ausente(db):
    _seed_customer(db)
    _seed_charge(db, payment_id="pay_chg_6", asaas_id="pay_only_by_id")
    db.commit()
    updated = svc.apply_webhook(
        db,
        {
            "event": "PAYMENT_RECEIVED",
            "payment": {"id": "pay_only_by_id"},  # sem externalReference
        },
    )
    assert updated.status == "PAID"


def test_webhook_event_payment_updated_no_op(db):
    _seed_customer(db)
    _seed_charge(db, payment_id="pay_chg_7", asaas_id="pay_upd")
    db.commit()
    result = svc.apply_webhook(
        db,
        {
            "event": "PAYMENT_UPDATED",
            "payment": {"id": "pay_upd", "externalReference": "pay_chg_7"},
        },
    )
    # PAYMENT_UPDATED nao muda status nem dispara notify
    assert result is None
    db.expire_all()
    assert db.query(Payment).filter_by(payment_id="pay_chg_7").one().status == "PENDING"


# ───────────────────────── cancel ──────────────────────────


def test_cancel_not_found(db, seeded_apikey, fake_asaas):
    with pytest.raises(svc.PaymentError, match="not_found"):
        svc.cancel(db, "pay_nao_existe")


def test_cancel_terminal_paid_falha(db, seeded_apikey, fake_asaas):
    _seed_customer(db)
    _seed_charge(db, payment_id="pay_paid", status="PAID")
    db.commit()
    with pytest.raises(svc.PaymentError, match="cannot_cancel_status"):
        svc.cancel(db, "pay_paid")


def test_cancel_cancelled_idempotente(db, seeded_apikey, fake_asaas):
    _seed_customer(db)
    _seed_charge(db, payment_id="pay_x", status="CANCELLED")
    db.commit()
    row = svc.cancel(db, "pay_x")
    assert row.status == "CANCELLED"


def test_cancel_pending_chama_asaas(db, seeded_apikey, fake_asaas):
    _seed_customer(db)
    _seed_charge(db, payment_id="pay_pend", status="PENDING", asaas_id="pay_remote_C")
    db.commit()
    fake_asaas.delete_payment.return_value = {"deleted": True}
    row = svc.cancel(db, "pay_pend")
    assert row.status == "CANCELLED"
    fake_asaas.delete_payment.assert_called_once_with("pay_remote_C")


def test_cancel_propaga_falha_asaas(db, seeded_apikey, fake_asaas):
    _seed_customer(db)
    _seed_charge(db, payment_id="pay_y", status="PENDING", asaas_id="pay_R")
    db.commit()
    fake_asaas.delete_payment.side_effect = AsaasError(400, {"err": "x"})
    with pytest.raises(svc.PaymentError, match="asaas_charge_delete_failed"):
        svc.cancel(db, "pay_y")


# ───────────────────────── refresh_qr ──────────────────────────


def test_refresh_qr_not_found(db, seeded_apikey, fake_asaas):
    with pytest.raises(svc.PaymentError, match="not_found"):
        svc.refresh_qr(db, "pay_nao_existe")


def test_refresh_qr_atualiza_campos(db, seeded_apikey, fake_asaas):
    _seed_customer(db)
    row = _seed_charge(db, asaas_id="pay_R")
    db.commit()
    fake_asaas.get_payment_pix_qr_code.return_value = {
        "encodedImage": "NEW_PNG",
        "payload": "NEW_PAYLOAD_00020126",
    }
    updated = svc.refresh_qr(db, row.payment_id)
    assert updated.qrcode_payload == "NEW_PAYLOAD_00020126"
    assert updated.pix_qr_image == "NEW_PNG"


# ───────────────────────── queries ──────────────────────────


def test_list_filtros(db, seeded_apikey, fake_asaas):
    _seed_customer(db)
    _seed_charge(db, payment_id="a", status="PENDING")
    _seed_charge(db, payment_id="b", status="PAID")
    _seed_charge(db, payment_id="c", status="PENDING")
    db.commit()
    pendings = svc.list_all(db, status="PENDING")
    assert {p.payment_id for p in pendings} == {"a", "c"}
    all_for_aluno = svc.list_all(db, external_id="aluno_42")
    assert len(all_for_aluno) == 3


def test_list_invalid_status_falha(db, fake_asaas):
    with pytest.raises(svc.PaymentError, match="invalid_status"):
        svc.list_all(db, status="WHATEVER")
