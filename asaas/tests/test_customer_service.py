"""Tests do app.services.customer — find-or-create, validacoes CPF/CNPJ."""

from __future__ import annotations

import pytest

from app.exceptions import ValidationError
from app.integrations.asaas_client import AsaasError
from app.models import Customer
from app.services import customer as svc


def _payer(name="Joao Pagador", cpf="07426367980", email=None, phone=None):
    return svc.PayerData(name=name, cpf_cnpj=cpf, email=email, mobile_phone=phone)


def _mock_asaas_customer(cust_id="cus_123", ext_id="aluno_42", cpf="07426367980"):
    return {
        "id": cust_id,
        "name": "Joao Pagador",
        "cpfCnpj": cpf,
        "email": "j@example.com",
        "mobilePhone": None,
        "externalReference": ext_id,
    }


def test_validate_cpf_cnpj_aceita_11_digitos():
    assert svc._validate_cpf_cnpj("074.263.679-80") == "07426367980"


def test_validate_cpf_cnpj_aceita_14_digitos():
    assert svc._validate_cpf_cnpj("12.345.678/0001-99") == "12345678000199"


def test_validate_cpf_cnpj_rejeita_outros():
    with pytest.raises(ValidationError, match="invalid_cpf_cnpj"):
        svc._validate_cpf_cnpj("12345")
    with pytest.raises(ValidationError, match="invalid_cpf_cnpj"):
        svc._validate_cpf_cnpj("")


def test_find_or_create_existing_local(db, seeded_apikey):
    """Customer ja persistido localmente — retorna sem chamar Asaas."""
    db.add(
        Customer(
            external_id="aluno_42",
            asaas_id="cus_existing",
            name="Pre Existing",
            cpf_cnpj="07426367980",
        )
    )
    db.commit()
    cust = svc.find_or_create(db, "aluno_42", payer=None)
    assert cust.asaas_id == "cus_existing"


def test_find_or_create_sem_payer_nem_local_falha(db, seeded_apikey):
    with pytest.raises(ValidationError, match="customer_required"):
        svc.find_or_create(db, "aluno_42", payer=None)


def test_find_or_create_external_id_vazio_falha(db, seeded_apikey):
    with pytest.raises(ValidationError, match="external_id_required"):
        svc.find_or_create(db, "  ", payer=_payer())


def test_find_or_create_sem_api_key_falha(db):
    with pytest.raises(ValidationError, match="asaas_api_key_not_set"):
        svc.find_or_create(db, "aluno_42", payer=_payer())


def test_find_or_create_recupera_do_asaas_por_external_reference(db, seeded_apikey, fake_asaas):
    """Customer existe no Asaas mas nao localmente — recupera e persiste."""
    fake_asaas.find_customer_by_external_reference.return_value = _mock_asaas_customer(
        cust_id="cus_recovered"
    )
    cust = svc.find_or_create(db, "aluno_42", payer=_payer())
    assert cust.asaas_id == "cus_recovered"
    # nao deve criar no Asaas porque ja existe
    fake_asaas.create_customer.assert_not_called()
    # confirma persistencia
    db.commit()
    assert db.query(Customer).filter_by(external_id="aluno_42").count() == 1


def test_find_or_create_cria_no_asaas(db, seeded_apikey, fake_asaas):
    fake_asaas.find_customer_by_external_reference.return_value = None
    fake_asaas.create_customer.return_value = _mock_asaas_customer(cust_id="cus_new")
    cust = svc.find_or_create(db, "aluno_42", payer=_payer())
    assert cust.asaas_id == "cus_new"
    fake_asaas.create_customer.assert_called_once()
    # confere que cpf foi normalizado pra so digitos
    call_payload = fake_asaas.create_customer.call_args[0][0]
    assert call_payload["cpfCnpj"] == "07426367980"
    assert call_payload["externalReference"] == "aluno_42"
    assert call_payload["notificationDisabled"] is True


def test_find_or_create_propaga_falha_asaas(db, seeded_apikey, fake_asaas):
    fake_asaas.find_customer_by_external_reference.return_value = None
    fake_asaas.create_customer.side_effect = AsaasError(
        400, {"errors": [{"code": "invalid_cpf", "description": "CPF invalido"}]}
    )
    with pytest.raises(ValidationError, match="asaas_customer_create_failed"):
        svc.find_or_create(db, "aluno_42", payer=_payer())


def test_get_by_asaas_id(db):
    db.add(
        Customer(
            external_id="x",
            asaas_id="cus_xyz",
            name="X",
            cpf_cnpj="11111111111",
        )
    )
    db.commit()
    assert svc.get_by_asaas_id(db, "cus_xyz").external_id == "x"
    assert svc.get_by_asaas_id(db, "nao_existe") is None
