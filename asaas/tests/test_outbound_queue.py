"""Tests da fila outbound_jobs (caminho do dinheiro — notify_internal -> worker)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.db import async_session_maker
from app.models import OutboundJob, Payment
from app.services import notifications
from app.workers import outbound_queue


def _mk_payment(kind: str = "charge", status: str = "PENDING", **extra) -> Payment:
    return Payment(payment_id="pay_test_1", kind=kind, status=status, amount=10.0, **extra)


# ───────────── enqueue ─────────────


async def test_enqueue_persiste_job_apos_commit(db):
    job_id = await outbound_queue.enqueue(
        db, url="http://x.local/", payload={"a": 1}, external_id="pay_test_1"
    )
    await db.commit()
    async with async_session_maker() as s:
        row = await s.get(OutboundJob, job_id)
    assert row is not None
    assert row.url == "http://x.local/"
    assert row.payload == {"a": 1}
    assert row.external_id == "pay_test_1"
    assert row.delivered_at is None
    assert row.attempts == 0
    assert row.max_attempts == len(outbound_queue.BACKOFF_SECONDS) + 1


async def test_enqueue_rollback_descarta_job(db):
    """Falha de transacao do caller cancela o enqueue — atomico no escopo do caller."""
    await outbound_queue.enqueue(db, url="http://x.local/", payload={}, external_id=None)
    await db.rollback()
    async with async_session_maker() as s:
        count = (await s.execute(select(OutboundJob))).scalars().all()
    assert count == []


# ───────────── notify_internal -> enqueue (fresh session) ─────────────


async def test_notify_internal_enqueia_em_sessao_propria(db):
    from app import config_store as cfg

    await cfg.set_(db, cfg.K_INTERNAL_URL_CHARGE, "http://charge.local/")
    await db.commit()

    p = _mk_payment(kind="charge", status="PENDING", customer_external_id="ext_1")
    await notifications.notify_internal(db, p)
    # Nota: db NUNCA foi committed por notify_internal — mas o job DEVE existir
    # porque notify_internal usa sessao propria.
    async with async_session_maker() as s:
        rows = (await s.execute(select(OutboundJob))).scalars().all()
    assert len(rows) == 1
    assert rows[0].url == "http://charge.local/"
    assert rows[0].payload["payment_id"] == "pay_test_1"
    assert rows[0].payload["status"] == "PENDING"
    assert rows[0].payload["kind"] == "charge"
    assert rows[0].payload["external_id"] == "ext_1"


# ───────────── worker delivery ─────────────


async def test_worker_entrega_2xx_marca_delivered(db, monkeypatch):
    job_id = await outbound_queue.enqueue(
        db, url="http://x.local/", payload={"k": "v"}, external_id=None
    )
    await db.commit()

    async def fake_deliver(url, payload):
        assert url == "http://x.local/"
        assert payload == {"k": "v"}
        return True, None, 200

    monkeypatch.setattr(outbound_queue, "_deliver_payload", fake_deliver)
    processed = await outbound_queue.process_due()
    assert processed == 1

    async with async_session_maker() as s:
        row = await s.get(OutboundJob, job_id)
    assert row.delivered_at is not None
    assert row.last_error is None
    assert row.attempts == 1


async def test_worker_retry_com_backoff_em_5xx(db, monkeypatch):
    job_id = await outbound_queue.enqueue(
        db, url="http://x.local/", payload={}, external_id=None
    )
    await db.commit()

    async with async_session_maker() as s:
        original_next_attempt = (await s.get(OutboundJob, job_id)).next_attempt_at

    async def fake_deliver(url, payload):
        return False, "HTTP 503: down", 503

    monkeypatch.setattr(outbound_queue, "_deliver_payload", fake_deliver)
    await outbound_queue.process_due()

    async with async_session_maker() as s:
        row = await s.get(OutboundJob, job_id)
    assert row.delivered_at is None
    assert row.attempts == 1
    assert "503" in (row.last_error or "")
    # backoff[0] = 60s → next_attempt empurrado pra frente (sqlite strip tz, comparacao naive vs naive)
    delta = (row.next_attempt_at - original_next_attempt).total_seconds()
    assert delta >= 55, f"expected >= 55s, got {delta}"


async def test_worker_exhausta_apos_max_attempts(db, monkeypatch):
    job_id = await outbound_queue.enqueue(
        db, url="http://x.local/", payload={}, external_id=None
    )
    await db.commit()
    # Avanca pra ja estar 1 abaixo do max
    async with async_session_maker() as s:
        j = await s.get(OutboundJob, job_id)
        j.attempts = j.max_attempts - 1
        await s.commit()

    async def fake_deliver(url, payload):
        return False, "timeout", None

    monkeypatch.setattr(outbound_queue, "_deliver_payload", fake_deliver)
    async with async_session_maker() as s:
        original_next_attempt = (await s.get(OutboundJob, job_id)).next_attempt_at
    await outbound_queue.process_due()

    async with async_session_maker() as s:
        row = await s.get(OutboundJob, job_id)
    assert row.delivered_at is None
    assert row.attempts >= row.max_attempts
    # exausto: pula 1 ano pra frente (>=300 dias acima do anterior)
    delta_days = (row.next_attempt_at - original_next_attempt).total_seconds() / 86400
    assert delta_days > 300, f"expected > 300 dias de delay, got {delta_days:.1f}"


async def test_worker_respeita_next_attempt_at_futuro(db, monkeypatch):
    """Job com next_attempt_at no futuro nao deve ser processado."""
    job_id = await outbound_queue.enqueue(
        db, url="http://x.local/", payload={}, external_id=None
    )
    await db.commit()
    async with async_session_maker() as s:
        j = await s.get(OutboundJob, job_id)
        j.next_attempt_at = datetime.now() + timedelta(hours=1)  # sqlite naive
        await s.commit()

    called = {"n": 0}

    async def fake_deliver(url, payload):
        called["n"] += 1
        return True, None, 200

    monkeypatch.setattr(outbound_queue, "_deliver_payload", fake_deliver)
    processed = await outbound_queue.process_due()
    assert processed == 0
    assert called["n"] == 0


# ───────────── claim atomico ─────────────


async def test_claim_atomico_nao_duplica_entrega(db, monkeypatch):
    """Dois process_due paralelos so entregam o job uma vez."""
    import asyncio

    job_id = await outbound_queue.enqueue(
        db, url="http://x.local/", payload={}, external_id=None
    )
    await db.commit()

    deliveries = {"n": 0}

    async def fake_deliver(url, payload):
        deliveries["n"] += 1
        await asyncio.sleep(0.01)
        return True, None, 200

    monkeypatch.setattr(outbound_queue, "_deliver_payload", fake_deliver)
    a, b = await asyncio.gather(
        outbound_queue.process_due(), outbound_queue.process_due()
    )
    # Um claimed e entregou, o outro pulou.
    assert (a, b) in ((1, 0), (0, 1))
    assert deliveries["n"] == 1
    async with async_session_maker() as s:
        row = await s.get(OutboundJob, job_id)
    assert row.delivered_at is not None


# ───────────── cleanup ─────────────


async def test_cleanup_remove_exauridos_antigos(db):
    job_id = await outbound_queue.enqueue(
        db, url="http://x.local/", payload={}, external_id=None
    )
    await db.commit()
    async with async_session_maker() as s:
        j = await s.get(OutboundJob, job_id)
        j.attempts = j.max_attempts
        j.updated_at = datetime.now() - timedelta(days=45)  # sqlite naive
        await s.commit()

    removed = await outbound_queue.cleanup_old_jobs(days=30)
    assert removed == 1
    async with async_session_maker() as s:
        remaining = (await s.execute(select(OutboundJob))).scalars().all()
    assert remaining == []


async def test_cleanup_preserva_jobs_recentes_e_entregues(db):
    j1 = await outbound_queue.enqueue(
        db, url="http://x.local/", payload={}, external_id=None
    )
    j2 = await outbound_queue.enqueue(
        db, url="http://y.local/", payload={}, external_id=None
    )
    await db.commit()
    async with async_session_maker() as s:
        a = await s.get(OutboundJob, j1)
        a.attempts = a.max_attempts
        a.updated_at = datetime.now() - timedelta(days=5)  # recente, sqlite naive
        b = await s.get(OutboundJob, j2)
        b.delivered_at = datetime.now() - timedelta(days=100)  # entregue antigo
        await s.commit()

    removed = await outbound_queue.cleanup_old_jobs(days=30)
    assert removed == 0
