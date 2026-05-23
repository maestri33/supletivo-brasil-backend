"""Tests do roteamento de internal notifications por categoria."""

from __future__ import annotations

from app import config_store as cfg
from app.models import Payment
from app.services import notifications


def _mk_payment(kind: str, status: str, **extra) -> Payment:
    return Payment(payment_id="pay_x", kind=kind, status=status, amount=1.0, **extra)


async def test_internal_url_for_charge_usa_charge_key(db):
    await cfg.set_(db, cfg.K_INTERNAL_URL_CHARGE, "http://charge.local/")
    await db.commit()
    assert (
        await notifications.internal_url_for(db, kind="charge", status="PENDING")
        == "http://charge.local/"
    )


async def test_internal_url_for_scheduling_usa_scheduling_key(db):
    await cfg.set_(db, cfg.K_INTERNAL_URL_SCHEDULING, "http://sched.local/")
    await db.commit()
    assert (
        await notifications.internal_url_for(db, kind="pixkey", status="SCHEDULED")
        == "http://sched.local/"
    )
    assert (
        await notifications.internal_url_for(db, kind="qrcode", status="QUEUED")
        == "http://sched.local/"
    )


async def test_internal_url_for_payout_usa_payout_key(db):
    await cfg.set_(db, cfg.K_INTERNAL_URL_PAYOUT, "http://payout.local/")
    await db.commit()
    for status in ("SUBMITTED", "PAID", "FAILED", "AWAITING_BALANCE", "CANCELLED"):
        assert (
            await notifications.internal_url_for(db, kind="pixkey", status=status)
            == "http://payout.local/"
        )
        assert (
            await notifications.internal_url_for(db, kind="qrcode", status=status)
            == "http://payout.local/"
        )


async def test_fallback_para_internal_url_legado(db):
    """Quando nao ha url especifica, cai no internal_url catch-all."""
    await cfg.set_(db, cfg.K_INTERNAL_URL, "http://legacy.local/")
    await db.commit()
    # nenhum especifico setado -> legacy
    assert (
        await notifications.internal_url_for(db, kind="charge", status="PAID")
        == "http://legacy.local/"
    )
    assert (
        await notifications.internal_url_for(db, kind="pixkey", status="SCHEDULED")
        == "http://legacy.local/"
    )
    assert (
        await notifications.internal_url_for(db, kind="qrcode", status="PAID")
        == "http://legacy.local/"
    )


async def test_especifico_tem_prioridade_sobre_legacy(db):
    await cfg.set_(db, cfg.K_INTERNAL_URL, "http://legacy.local/")
    await cfg.set_(db, cfg.K_INTERNAL_URL_CHARGE, "http://charge.local/")
    await db.commit()
    assert (
        await notifications.internal_url_for(db, kind="charge", status="PAID")
        == "http://charge.local/"
    )
    # pixkey ainda cai no legacy (charge nao impacta)
    assert (
        await notifications.internal_url_for(db, kind="pixkey", status="PAID")
        == "http://legacy.local/"
    )


async def test_sem_nenhuma_url_retorna_none(db):
    assert await notifications.internal_url_for(db, kind="pixkey", status="PAID") is None
    assert await notifications.internal_url_for(db, kind="charge", status="PENDING") is None


def test_external_id_field_routing():
    p_pix = _mk_payment("pixkey", "PAID", pixkey_external_id="vic_celular")
    p_qr = _mk_payment("qrcode", "PAID")
    p_ch = _mk_payment("charge", "PENDING", customer_external_id="aluno_42")
    assert notifications._external_id_field(p_pix) == "vic_celular"
    assert notifications._external_id_field(p_qr) is None
    assert notifications._external_id_field(p_ch) == "aluno_42"


async def test_notify_internal_no_op_quando_sem_url(db):
    """Sem URL configurada, nao explode (apenas log)."""
    p = _mk_payment("charge", "PENDING", customer_external_id="x")
    p.payment_id = "pay_test"
    # nao deve raise
    await notifications.notify_internal(db, p)
