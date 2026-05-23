"""Tests do parser BR Code EMVCo. Funcoes puras, sem fixtures."""

from __future__ import annotations

from app.utils.brcode import analyze, extract_amount, is_dynamic, parse_tlv

# QR estatico real, valor R$ 0,01, chave PIX +5542999384069 (telefone)
STATIC_FIXED = (
    "00020126360014BR.GOV.BCB.PIX0114+554299938406952040000530398654040.01"
    "5802BR5925VICTOR VANDERLEY MAESTRI6014SANTO ANT PLATI62070503***6304"
)

# QR estatico, sem valor (variavel)
STATIC_VARIABLE = (
    "00020126360014BR.GOV.BCB.PIX0114+55429993840695204000053039865802BR"
    "5925VICTOR VANDERLEY MAESTRI6014SANTO ANT PLATI62070503***6304"
)

# QR dinamico (subtag 25 com URL no merchant_account)
DYNAMIC = (
    "00020101021226780014br.gov.bcb.pix2556qrcodepix.example.com/qr/v2/abc"
    "5204000053039865802BR5913MERCHANT NAME6008CITY    62070503***6304"
)


def test_parse_tlv_extrai_campos_topo():
    fields = parse_tlv(STATIC_FIXED)
    assert "26" in fields  # merchant account
    assert "54" in fields  # amount
    assert fields["54"] == "0.01"


def test_extract_amount_qr_fixo():
    assert extract_amount(STATIC_FIXED) == 0.01


def test_extract_amount_qr_variavel():
    assert extract_amount(STATIC_VARIABLE) is None


def test_is_dynamic_static():
    assert is_dynamic(STATIC_FIXED) is False


def test_is_dynamic_dynamic():
    assert is_dynamic(DYNAMIC) is True


def test_analyze_static_fixed():
    a = analyze(STATIC_FIXED)
    assert a["valid_tlv"] is True
    assert a["kind"] == "static"
    assert a["amount"] == 0.01
    assert a["allows_amount_edit"] is False
    assert a["can_schedule"] is True
    assert a["pix_key"] == "+5542999384069"
    assert a["dynamic_url"] is None


def test_analyze_static_variable():
    a = analyze(STATIC_VARIABLE)
    assert a["kind"] == "static"
    assert a["amount"] is None
    assert a["allows_amount_edit"] is True
    assert a["can_schedule"] is True
    assert "amount_not_fixed" in a["warnings"]


def test_analyze_dynamic_blocks_schedule():
    a = analyze(DYNAMIC)
    assert a["kind"] == "dynamic"
    assert a["can_schedule"] is False
    assert a["dynamic_url"] is not None
    assert "scheduled_dynamic_qrcode_not_supported" in a["warnings"]


def test_analyze_invalid_short_returns_invalid_tlv():
    a = analyze("xxx")
    assert a["valid_tlv"] is False
    assert a["amount"] is None


def test_analyze_lixo_total():
    """Garbage não deve quebrar — devolve estrutura vazia/segura."""
    a = analyze("00aabbccddeeff!!@@")
    # campo 00 com 'aa' length faz parser pular; pode ou nao registrar campos
    assert isinstance(a["warnings"], list)
    assert a["amount"] is None or isinstance(a["amount"], float)
