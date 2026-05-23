"""Tests do Mecanismo de Validacao de Saque (POST /security-validator)."""

from __future__ import annotations

from app.models import Payment, PixKey
from app.services import security_validator


async def _seed_payout(db, *, kind="pixkey", asaas_id="tr_abc", amount=10.0, status="SUBMITTED"):
    if kind == "pixkey":
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
    row = Payment(
        payment_id=f"pay_{asaas_id}",
        kind=kind,
        pixkey_external_id="x" if kind == "pixkey" else None,
        qrcode_payload="00020126..." if kind == "qrcode" else None,
        amount=amount,
        status=status,
        asaas_id=asaas_id,
    )
    db.add(row)
    await db.flush()
    return row


# ───────────────────── validate() unitario ─────────────────────


async def test_validate_aprova_transfer_match(db):
    await _seed_payout(db, kind="pixkey", asaas_id="tr_match", amount=12.34)
    await db.commit()
    approved, reason = await security_validator.validate(
        db,
        {"type": "TRANSFER", "transfer": {"id": "tr_match", "value": 12.34}},
    )
    assert approved is True
    assert reason is None


async def test_validate_aprova_pix_qr_code_match(db):
    await _seed_payout(db, kind="qrcode", asaas_id="pix_match", amount=1.5)
    await db.commit()
    approved, reason = await security_validator.validate(
        db,
        {"type": "PIX_QR_CODE", "pixQrCode": {"id": "pix_match", "value": 1.5}},
    )
    assert approved is True
    assert reason is None


async def test_validate_recusa_value_mismatch(db):
    await _seed_payout(db, kind="pixkey", asaas_id="tr_mm", amount=10.0)
    await db.commit()
    approved, reason = await security_validator.validate(
        db,
        {"type": "TRANSFER", "transfer": {"id": "tr_mm", "value": 99.99}},
    )
    assert approved is False
    assert "value_mismatch" in reason


async def test_validate_recusa_id_desconhecido(db):
    approved, reason = await security_validator.validate(
        db,
        {"type": "TRANSFER", "transfer": {"id": "id_que_nao_existe", "value": 1.0}},
    )
    assert approved is False
    assert "operation_not_found_locally" in reason


async def test_validate_recusa_kind_errado(db):
    """qrcode no DB mas Asaas mandou TRANSFER — nao bate kind."""
    await _seed_payout(db, kind="qrcode", asaas_id="pix_x", amount=10.0)
    await db.commit()
    approved, reason = await security_validator.validate(
        db, {"type": "TRANSFER", "transfer": {"id": "pix_x", "value": 10.0}}
    )
    assert approved is False
    assert "operation_not_found_locally" in reason


async def test_validate_recusa_status_paid_ja_concluido(db):
    """Apenas SUBMITTING/SUBMITTED sao validaveis. PAID, FAILED, etc nao."""
    await _seed_payout(db, kind="pixkey", asaas_id="tr_old", amount=5.0, status="PAID")
    await db.commit()
    approved, reason = await security_validator.validate(
        db, {"type": "TRANSFER", "transfer": {"id": "tr_old", "value": 5.0}}
    )
    assert approved is False


async def test_validate_aprova_status_submitting(db):
    """Janela curta entre claim e response do Asaas — SUBMITTING e valido."""
    await _seed_payout(db, kind="pixkey", asaas_id="tr_subm", amount=2.0, status="SUBMITTING")
    await db.commit()
    approved, reason = await security_validator.validate(
        db, {"type": "TRANSFER", "transfer": {"id": "tr_subm", "value": 2.0}}
    )
    assert approved is True


async def test_validate_recusa_bill(db):
    approved, reason = await security_validator.validate(
        db, {"type": "BILL", "bill": {"id": 1, "value": 50}}
    )
    assert approved is False
    assert "unsupported_operation_type: BILL" in reason


async def test_validate_recusa_pix_refund(db):
    approved, reason = await security_validator.validate(
        db, {"type": "PIX_REFUND", "pixRefund": {"id": "abc"}}
    )
    assert approved is False
    assert "unsupported_operation_type: PIX_REFUND" in reason


async def test_validate_recusa_mobile_recharge(db):
    approved, reason = await security_validator.validate(
        db, {"type": "MOBILE_PHONE_RECHARGE", "mobilePhoneRecharge": {"id": "x"}}
    )
    assert approved is False


async def test_validate_recusa_type_desconhecido(db):
    approved, reason = await security_validator.validate(db, {"type": "INVENTED"})
    assert approved is False
    assert "unknown_type" in reason


async def test_validate_recusa_sem_type(db):
    approved, reason = await security_validator.validate(db, {"transfer": {"id": "x"}})
    assert approved is False
    assert "missing_type" in reason


async def test_validate_recusa_payload_nao_dict(db):
    approved, reason = await security_validator.validate(db, "not a dict")  # type: ignore[arg-type]
    assert approved is False
    assert "invalid_payload" in reason


async def test_validate_recusa_sem_id_no_payload(db):
    approved, reason = await security_validator.validate(
        db, {"type": "TRANSFER", "transfer": {"value": 10}}
    )
    assert approved is False
    assert "missing_id_in_payload" in reason


async def test_validate_recusa_sem_objeto_transfer(db):
    approved, reason = await security_validator.validate(db, {"type": "TRANSFER"})
    assert approved is False
    assert "missing_transfer_object" in reason


async def test_validate_value_sem_value_no_payload_ainda_aprova(db):
    """Se Asaas nao mandar value, validamos so por ID (defensive)."""
    await _seed_payout(db, kind="pixkey", asaas_id="tr_no_val", amount=42.0)
    await db.commit()
    approved, _ = await security_validator.validate(
        db, {"type": "TRANSFER", "transfer": {"id": "tr_no_val"}}
    )
    assert approved is True


# ───────────────────── decide() (wrapper que retorna body) ─────────────────────


async def test_decide_aprovado_retorna_status(db):
    await _seed_payout(db, kind="pixkey", asaas_id="tr_dec", amount=7.0)
    await db.commit()
    body = await security_validator.decide(
        db, {"type": "TRANSFER", "transfer": {"id": "tr_dec", "value": 7.0}}
    )
    assert body == {"status": "APPROVED"}


async def test_decide_refusa_retorna_status_e_reason(db):
    body = await security_validator.decide(db, {"type": "TRANSFER", "transfer": {"id": "x"}})
    assert body["status"] == "REFUSED"
    assert "refuseReason" in body


# ───────────────────── integracao via HTTP ─────────────────────


async def test_http_security_validator_aprova_transfer_match(db, client, seeded_token):
    await _seed_payout(db, kind="pixkey", asaas_id="tr_http", amount=20.0)
    await db.commit()
    r = await client.post(
        "/security-validator",
        json={"type": "TRANSFER", "transfer": {"id": "tr_http", "value": 20.0}},
        headers={"asaas-access-token": seeded_token},
    )
    assert r.status_code == 200
    assert r.json() == {"status": "APPROVED"}


async def test_http_security_validator_recusa_value_mismatch(db, client, seeded_token):
    await _seed_payout(db, kind="pixkey", asaas_id="tr_http2", amount=10.0)
    await db.commit()
    r = await client.post(
        "/security-validator",
        json={"type": "TRANSFER", "transfer": {"id": "tr_http2", "value": 999.0}},
        headers={"asaas-access-token": seeded_token},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "REFUSED"
    assert "value_mismatch" in body["refuseReason"]


async def test_http_security_validator_recusa_bill_sempre(db, client, seeded_token):
    r = await client.post(
        "/security-validator",
        json={"type": "BILL", "bill": {"id": 1, "value": 50}},
        headers={"asaas-access-token": seeded_token},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "REFUSED"
