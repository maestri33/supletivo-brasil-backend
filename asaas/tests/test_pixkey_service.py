"""Tests do app.services.pixkey — validacao, dedup e fluxo DICT mockado."""

from __future__ import annotations

import pytest

from app.integrations.asaas_client import AsaasError
from app.services import pixkey as svc

# ───────────────────────── validacao de formato ──────────────────────────


@pytest.mark.parametrize(
    "key,kt,expected",
    [
        ("123", "CPF", "invalid_cpf_format"),
        ("12345678901abc", "CPF", "invalid_cpf_format"),
        ("123", "CNPJ", "invalid_cnpj_format"),
        ("foo", "EMAIL", "invalid_email_format"),
        ("foo@bar", "EMAIL", "invalid_email_format"),
        ("552998", "PHONE", "invalid_phone_format"),  # sem +
        ("not-a-uuid", "EVP", "invalid_evp_format"),
        ("11111111111", "FOO", "invalid_key_type"),
    ],
)
def test_basic_validate_rejeita_formatos_invalidos(key, kt, expected):
    with pytest.raises(svc.PixKeyError) as ei:
        svc._basic_validate(key, kt)
    assert expected in str(ei.value)


def test_basic_validate_aceita_formatos_corretos():
    svc._basic_validate("12345678901", "CPF")
    svc._basic_validate("12345678000199", "CNPJ")
    svc._basic_validate("foo@bar.com", "EMAIL")
    svc._basic_validate("+5542999384069", "PHONE")
    svc._basic_validate("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "EVP")


# ───────────────────────── create() ──────────────────────────


def test_create_sem_apikey_falha(db):
    with pytest.raises(svc.PixKeyError, match="asaas_api_key_not_set"):
        svc.create(db, "ext1", "12345678901", "12345678901", "CPF")


def test_create_external_id_vazio(db, seeded_apikey):
    with pytest.raises(svc.PixKeyError, match="external_id_required"):
        svc.create(db, "  ", "12345678901", "12345678901", "CPF")


def test_create_doc_invalido(db, seeded_apikey):
    with pytest.raises(svc.PixKeyError, match="invalid_document_length"):
        svc.create(db, "ext1", "1234", "12345678901", "CPF")


def _mock_dict_response(doc="12345678901", name="TESTE", bank="INTER"):
    return {
        "id": "tr_fake_1",
        "bankAccount": {
            "cpfCnpj": doc,
            "ownerName": name,
            "bank": {"name": bank},
        },
    }


def test_create_sucesso(db, seeded_apikey, fake_asaas):
    fake_asaas.create_transfer.return_value = _mock_dict_response()
    fake_asaas.cancel_transfer.return_value = None

    row = svc.create(db, "ext1", "12345678901", "12345678901", "CPF")
    db.commit()

    assert row.external_id == "ext1"
    assert row.holder_name == "TESTE"
    assert row.bank_name == "INTER"
    # garante que cancelou a transfer de validacao
    fake_asaas.cancel_transfer.assert_called_once_with("tr_fake_1")


def test_create_dedup_external_id(db, seeded_apikey, fake_asaas):
    fake_asaas.create_transfer.return_value = _mock_dict_response()
    svc.create(db, "ext1", "12345678901", "12345678901", "CPF")
    db.commit()

    # mesmo external_id, chave diferente
    with pytest.raises(svc.PixKeyError, match="external_id_already_exists"):
        svc.create(db, "ext1", "98765432100", "98765432100", "CPF")


def test_create_dedup_pix_key(db, seeded_apikey, fake_asaas):
    fake_asaas.create_transfer.return_value = _mock_dict_response()
    svc.create(db, "ext1", "12345678901", "12345678901", "CPF")
    db.commit()

    # external_id diferente, mas mesma chave
    with pytest.raises(svc.PixKeyError, match="pix_key_already_registered"):
        svc.create(db, "ext2", "12345678901", "12345678901", "CPF")


def test_create_holder_mismatch(db, seeded_apikey, fake_asaas):
    fake_asaas.create_transfer.return_value = _mock_dict_response(doc="99999999999")
    with pytest.raises(svc.PixKeyError, match="holder_mismatch"):
        svc.create(db, "ext1", "12345678901", "12345678901", "CPF")


def test_create_dict_lookup_fail(db, seeded_apikey, fake_asaas):
    fake_asaas.create_transfer.side_effect = AsaasError(
        400, {"errors": [{"description": "key not found"}]}
    )
    with pytest.raises(svc.PixKeyError, match="dict_lookup_failed"):
        svc.create(db, "ext1", "12345678901", "12345678901", "CPF")


# ───────────────────────── check() ──────────────────────────


def test_check_db_first(db, seeded_apikey, fake_asaas):
    fake_asaas.create_transfer.return_value = _mock_dict_response()
    svc.create(db, "ext1", "12345678901", "12345678901", "CPF")
    db.commit()
    fake_asaas.create_transfer.reset_mock()

    result = svc.check(db, "12345678901")
    assert result["source"] == "db"
    assert result["data"]["external_id"] == "ext1"
    fake_asaas.create_transfer.assert_not_called()


def test_check_dict_fallback(db, seeded_apikey, fake_asaas):
    fake_asaas.create_transfer.return_value = _mock_dict_response(doc="55555555555", name="OUTRO")
    result = svc.check(db, "55555555555")
    assert result["source"] == "dict"
    assert result["data"]["holder_name"] == "OUTRO"
    fake_asaas.create_transfer.assert_called_once()
