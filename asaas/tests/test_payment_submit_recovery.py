"""Tests do caminho do dinheiro: idempotencia, erro de rede e reconciliacao de stale.

Cobrem a logica de submit_one/tick com o AsaasClient mockado (fake_asaas). O cenario
real de duplicata contra Postgres vive em tests_pg/ (integracao) — aqui validamos os
ramos de decisao sem depender do banco real.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import update

from app.integrations.asaas_client import AsaasError
from app.models import Payment, PixKey
from app.services import payment as svc

# QR Code estatico de valor fixo (0.01) reusado do test_brcode
from tests.test_brcode import STATIC_FIXED


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


async def _make_stale_submitting(db, payment: Payment) -> None:
    """Forca o payment pra SUBMITTING travado (asaas_id NULL, updated_at vencido)."""
    stale_ts = datetime.now(UTC) - (svc.SUBMITTING_STALE_AFTER + timedelta(minutes=1))
    await db.execute(
        update(Payment)
        .where(Payment.id == payment.id)
        .values(status="SUBMITTING", asaas_id=None, updated_at=stale_ts)
    )
    await db.commit()


# ───────────────────── submit_one: erro de rede ─────────────────────


async def test_submit_one_network_error_keeps_submitting(db, seeded_apikey, fake_asaas):
    """Timeout/conexao nao marca FAILED nem reenfileira: fica SUBMITTING pro stale."""
    await _seed_pixkey(db)
    p = await svc.create_pixkey(db, "ext1", 1.0)
    await db.commit()
    fake_asaas.create_transfer.side_effect = httpx.ConnectError("boom")

    await svc.submit_one(db, p)  # nao deve propagar

    await db.refresh(p)
    assert p.status == "SUBMITTING"
    assert p.asaas_id is None
    assert p.last_error and "submit_uncertain" in p.last_error
    _, kwargs = fake_asaas.create_transfer.call_args
    assert kwargs.get("idempotency_key") == p.payment_id


# ───────────────────── submit_one: conflito 409 ─────────────────────


async def test_submit_one_409_pixkey_adopts_existing(db, seeded_apikey, fake_asaas):
    """409 (ja submetida) em pixkey: adota a transfer existente, nao cria outra."""
    await _seed_pixkey(db)
    p = await svc.create_pixkey(db, "ext1", 1.0)
    await db.commit()
    fake_asaas.create_transfer.side_effect = AsaasError(409, None)
    fake_asaas.list_transfers.return_value = {
        "data": [{"id": "tr_existing", "externalReference": p.payment_id}],
        "hasMore": False,
    }

    await svc.submit_one(db, p)

    await db.refresh(p)
    assert p.status == "SUBMITTED"
    assert p.asaas_id == "tr_existing"


async def test_submit_one_409_pixkey_pending_when_not_listed(db, seeded_apikey, fake_asaas):
    """409 mas a transfer ainda nao aparece na listagem: SUBMITTED sem asaas_id."""
    await _seed_pixkey(db)
    p = await svc.create_pixkey(db, "ext1", 1.0)
    await db.commit()
    fake_asaas.create_transfer.side_effect = AsaasError(409, None)
    fake_asaas.list_transfers.return_value = {"data": [], "hasMore": False}

    await svc.submit_one(db, p)

    await db.refresh(p)
    assert p.status == "SUBMITTED"
    assert p.asaas_id is None
    assert "idempotent_conflict_pending_reconcile" in p.last_error


async def test_submit_one_409_qrcode_needs_reconcile(db, seeded_apikey, fake_asaas):
    """409 em qrcode: sem externalReference na pix transaction -> NEEDS_RECONCILE manual."""
    p = await svc.create_qrcode(db, STATIC_FIXED, amount=0.01)
    await db.commit()
    fake_asaas.pay_qr_code.side_effect = AsaasError(409, None)

    await svc.submit_one(db, p)

    await db.refresh(p)
    assert p.status == "NEEDS_RECONCILE"
    assert "qrcode_idempotent_conflict_manual" in p.last_error
    _, kwargs = fake_asaas.pay_qr_code.call_args
    assert kwargs.get("idempotency_key") == p.payment_id


async def test_submit_one_insufficient_balance_still_awaits(db, seeded_apikey, fake_asaas):
    """Regressao: saldo insuficiente continua indo pra AWAITING_BALANCE."""
    await _seed_pixkey(db)
    p = await svc.create_pixkey(db, "ext1", 1.0)
    await db.commit()
    fake_asaas.create_transfer.side_effect = AsaasError(
        400, {"errors": [{"description": "Saldo insuficiente para realizar a operação."}]}
    )

    await svc.submit_one(db, p)

    await db.refresh(p)
    assert p.status == "AWAITING_BALANCE"


# ───────────────────── tick: requeue de stale ─────────────────────


async def test_tick_stale_pixkey_adopts_no_duplicate(db, seeded_apikey, fake_asaas):
    """Cerne do fix: pixkey travado cuja transfer ja existe e ADOTADA, sem re-submeter."""
    await _seed_pixkey(db)
    p = await svc.create_pixkey(db, "ext1", 1.0)
    await db.commit()
    await _make_stale_submitting(db, p)
    fake_asaas.list_transfers.return_value = {
        "data": [{"id": "tr_orig", "externalReference": p.payment_id}],
        "hasMore": False,
    }
    fake_asaas.get_transfer.return_value = {"status": "PENDING", "failReason": None}

    await svc.tick(db)

    await db.refresh(p)
    assert p.status == "SUBMITTED"
    assert p.asaas_id == "tr_orig"
    fake_asaas.create_transfer.assert_not_called()  # nao gerou transferencia duplicada


async def test_tick_stale_pixkey_requeues_and_resubmits_once(db, seeded_apikey, fake_asaas):
    """Se a transfer nao existe, reenfileira e re-submete UMA vez (com idempotency-key)."""
    await _seed_pixkey(db)
    p = await svc.create_pixkey(db, "ext1", 1.0)
    await db.commit()
    await _make_stale_submitting(db, p)
    fake_asaas.list_transfers.return_value = {"data": [], "hasMore": False}
    fake_asaas.create_transfer.return_value = {"id": "tr_new"}
    fake_asaas.get_transfer.return_value = {"status": "PENDING", "failReason": None}

    await svc.tick(db)

    await db.refresh(p)
    assert p.status == "SUBMITTED"
    assert p.asaas_id == "tr_new"
    fake_asaas.create_transfer.assert_called_once()
    _, kwargs = fake_asaas.create_transfer.call_args
    assert kwargs.get("idempotency_key") == p.payment_id
