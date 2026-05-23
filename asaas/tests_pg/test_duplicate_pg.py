"""Integracao Postgres: o caminho do dinheiro NAO duplica apos timeout.

Reproduz contra o banco real (commits/timestamptz/schema reais — o que o SQLite
mascara) o cenario do bug: claim commitado, depois timeout na chamada ao Asaas. O
proximo tick reconcilia por externalReference e adota a transfer existente, sem
re-submeter.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import update

from app import config_store as cfg
from app.models import Payment, PixKey
from app.services import payment as svc

pytestmark = pytest.mark.skipif(
    not os.environ.get("ASAAS_TEST_PG_URL"), reason="ASAAS_TEST_PG_URL nao definido"
)


async def _seed(db) -> None:
    await cfg.set_(db, cfg.K_ASAAS_API_KEY, "$aact_hmlg_test_key")
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


async def _make_stale(db, payment: Payment) -> None:
    await db.execute(
        update(Payment)
        .where(Payment.id == payment.id)
        .values(updated_at=datetime.now(UTC) - (svc.SUBMITTING_STALE_AFTER + timedelta(minutes=1)))
    )
    await db.commit()


async def test_timeout_after_create_does_not_duplicate(db, fake_asaas):
    """(a) timeout apos create_transfer + (b) adocao por externalReference no proximo tick."""
    await _seed(db)
    p = await svc.create_pixkey(db, "ext1", 1.0)
    await db.commit()

    # 1) 1a tentativa: a resposta se perde (timeout). A transfer PODE ter sido criada.
    fake_asaas.create_transfer.side_effect = httpx.ReadTimeout("timeout")
    await svc.submit_one(db, p)
    await db.refresh(p)
    assert p.status == "SUBMITTING"  # claim persistiu no PG, sem propagar a excecao
    assert p.asaas_id is None
    assert fake_asaas.create_transfer.call_count == 1

    # 2) a transfer original DE FATO existe no Asaas (so a resposta se perdeu)
    fake_asaas.list_transfers.return_value = {
        "data": [{"id": "tr_real", "externalReference": p.payment_id}],
        "hasMore": False,
    }
    fake_asaas.get_transfer.return_value = {"status": "PENDING", "failReason": None}

    # 3) claim vira stale -> proximo tick reconcilia
    await _make_stale(db, p)
    await svc.tick(db)

    await db.refresh(p)
    assert p.status == "SUBMITTED"
    assert p.asaas_id == "tr_real"  # adotou a transfer existente (externalReference)
    assert fake_asaas.create_transfer.call_count == 1  # NAO re-submeteu -> sem duplicata


async def test_timeout_then_requeue_when_transfer_absent(db, fake_asaas):
    """Timeout sem transfer criada: reconciliacao confirma ausencia e re-submete uma vez."""
    await _seed(db)
    p = await svc.create_pixkey(db, "ext1", 1.0)
    await db.commit()

    fake_asaas.create_transfer.side_effect = httpx.ReadTimeout("timeout")
    await svc.submit_one(db, p)
    await db.refresh(p)
    assert p.status == "SUBMITTING"
    assert fake_asaas.create_transfer.call_count == 1

    # a transfer NAO existe no Asaas -> reconciliacao confirma ausencia -> re-submete (200)
    fake_asaas.create_transfer.side_effect = None
    fake_asaas.create_transfer.return_value = {"id": "tr_after_requeue"}
    fake_asaas.list_transfers.return_value = {"data": [], "hasMore": False}
    fake_asaas.get_transfer.return_value = {"status": "PENDING", "failReason": None}

    await _make_stale(db, p)
    await svc.tick(db)

    await db.refresh(p)
    assert p.status == "SUBMITTED"
    assert p.asaas_id == "tr_after_requeue"
    assert fake_asaas.create_transfer.call_count == 2  # 1a (timeout) + re-submit unico
