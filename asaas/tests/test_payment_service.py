"""Tests do app.services.payment — validacoes, regras de QR e cancel."""

from __future__ import annotations

import pytest

from app.models import Payment, PixKey
from app.services import payment as svc

# Reusa BR Codes do test_brcode
from tests.test_brcode import DYNAMIC, STATIC_FIXED, STATIC_VARIABLE


async def _seed_pixkey(db, ext_id="ext1") -> PixKey:
    row = PixKey(
        external_id=ext_id,
        key=f"key-{ext_id}",
        key_type="CPF",
        holder_document="12345678901",
        holder_name="TESTE",
        bank_name="INTER",
    )
    db.add(row)
    await db.flush()
    return row


# ───────────────────────── create_pixkey ──────────────────────────


async def test_create_pixkey_invalid_amount(db):
    await _seed_pixkey(db)
    with pytest.raises(svc.PaymentError, match="invalid_amount"):
        await svc.create_pixkey(db, "ext1", -1.0)
    with pytest.raises(svc.PaymentError, match="invalid_amount"):
        await svc.create_pixkey(db, "ext1", 0.0)


async def test_create_pixkey_not_found(db):
    with pytest.raises(svc.PaymentError, match="pixkey_not_found"):
        await svc.create_pixkey(db, "no_exist", 1.0)


async def test_create_pixkey_imediato_status_queued(db):
    await _seed_pixkey(db)
    p = await svc.create_pixkey(db, "ext1", 1.50)
    assert p.status == "QUEUED"
    assert p.scheduled_for is None
    assert p.payment_id.startswith("pay_")


async def test_create_pixkey_agendado_status_scheduled(db):
    await _seed_pixkey(db)
    p = await svc.create_pixkey(db, "ext1", 1.50, schedule_date="2030-12-31", hour=10)
    assert p.status == "SCHEDULED"
    assert p.scheduled_for is not None


async def test_create_pixkey_data_invalida(db):
    await _seed_pixkey(db)
    with pytest.raises(svc.PaymentError, match="invalid_date"):
        await svc.create_pixkey(db, "ext1", 1.50, schedule_date="2030-13-99")


async def test_create_pixkey_idempotencia_payment_id(db):
    await _seed_pixkey(db)
    await svc.create_pixkey(db, "ext1", 1.0, payment_id="custom_id_1")
    await db.commit()
    with pytest.raises(svc.PaymentError, match="payment_id_already_exists"):
        await svc.create_pixkey(db, "ext1", 1.0, payment_id="custom_id_1")


# ───────────────────────── create_qrcode ──────────────────────────


async def test_create_qrcode_payload_curto(db):
    with pytest.raises(svc.PaymentError, match="invalid_qrcode_payload"):
        await svc.create_qrcode(db, "xx", 1.0)


async def test_create_qrcode_valor_fixo_aceita_sem_amount(db):
    p = await svc.create_qrcode(db, STATIC_FIXED, amount=None)
    assert p.amount == 0.01
    assert p.kind == "qrcode"


async def test_create_qrcode_valor_fixo_aceita_amount_igual(db):
    p = await svc.create_qrcode(db, STATIC_FIXED, amount=0.01)
    assert p.amount == 0.01


async def test_create_qrcode_valor_fixo_rejeita_amount_diferente(db):
    with pytest.raises(svc.PaymentError, match="qrcode_fixed_amount_mismatch"):
        await svc.create_qrcode(db, STATIC_FIXED, amount=10.0)


async def test_create_qrcode_variavel_exige_amount(db):
    with pytest.raises(svc.PaymentError, match="qrcode_amount_required"):
        await svc.create_qrcode(db, STATIC_VARIABLE, amount=None)


async def test_create_qrcode_variavel_amount_invalido(db):
    with pytest.raises(svc.PaymentError, match="invalid_amount"):
        await svc.create_qrcode(db, STATIC_VARIABLE, amount=-5.0)


async def test_create_qrcode_dinamico_bloqueia_agendamento(db):
    with pytest.raises(svc.PaymentError, match="dynamic_qrcode_scheduling_not_supported"):
        await svc.create_qrcode(db, DYNAMIC, amount=1.0, schedule_date="2030-12-31")


async def test_create_qrcode_dinamico_imediato_ok(db):
    """Dinamico pode pagar agora, so nao pode agendar."""
    p = await svc.create_qrcode(db, DYNAMIC, amount=5.0)
    assert p.status == "QUEUED"
    assert p.amount == 5.0


# ───────────────────────── cancel ──────────────────────────


async def _new_payment(db, status="SCHEDULED") -> Payment:
    await _seed_pixkey(db)
    p = await svc.create_pixkey(db, "ext1", 1.0)
    p.status = status
    await db.flush()
    return p


async def test_cancel_not_found(db):
    with pytest.raises(svc.PaymentError, match="not_found"):
        await svc.cancel(db, "no_existe")


@pytest.mark.parametrize("status", ["SCHEDULED", "QUEUED", "AWAITING_BALANCE"])
async def test_cancel_local_marca_cancelled(db, status):
    p = await _new_payment(db, status=status)
    out = await svc.cancel(db, p.payment_id)
    assert out.status == "CANCELLED"


@pytest.mark.parametrize("status", ["PAID", "FAILED", "CANCELLED"])
async def test_cancel_idempotente_em_terminal(db, status):
    """Cancelar em terminal nao raise — devolve o row inalterado."""
    p = await _new_payment(db, status=status)
    out = await svc.cancel(db, p.payment_id)
    assert out.status == status  # nao mudou


# ───────────────────────── to_dict ──────────────────────────


async def test_to_dict_serializa_campos_chave(db):
    await _seed_pixkey(db)
    p = await svc.create_pixkey(db, "ext1", 2.50, description="x")
    d = svc.to_dict(p)
    assert d["payment_id"] == p.payment_id
    assert d["status"] == "QUEUED"
    assert d["amount"] == 2.50
    assert d["description"] == "x"
    assert d["kind"] == "pixkey"
    assert d["asaas_id"] is None
