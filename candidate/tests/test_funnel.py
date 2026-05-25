"""Testes do funil do candidate — transicoes de status e gates."""

from uuid import uuid4

from sqlalchemy import select

from app.db import async_session_maker
from app.models import Candidate


async def test_register_creates_candidate(client, mocks):
    ext = uuid4()
    mocks.auth.register.return_value = {"external_id": str(ext)}

    resp = await client.post(
        "/api/v1/public/register",
        json={"phone": "42999999999", "cpf": "07461638947"},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["external_id"] == str(ext)

    async with async_session_maker() as session:
        candidate = await session.scalar(
            select(Candidate).where(Candidate.external_id == str(ext))
        )
    assert candidate is not None
    assert candidate.status == "captured"


async def test_wrong_status_is_gated(client, make_candidate, login_as, mocks):
    ext = await make_candidate(status="personal")
    login_as(ext)
    resp = await client.get("/api/v1/authenticated/captured")
    assert resp.status_code == 403


async def test_full_funnel_until_completed(client, make_candidate, login_as, mocks):
    hub = uuid4()
    ext = await make_candidate(status="captured", hub=hub)
    login_as(ext)

    mocks.profiles.patch.return_value = {}
    mocks.profiles.first_name.return_value = {"first_name": "Joao"}
    mocks.profiles.get_one.return_value = {
        "gender": "M",
        "mother_name": "Maria",
        "father_name": "Jose",
        "marital_status": "solteiro",
        "education_level": "superior",
        "institution": "UFPR",
        "course": "ADM",
        "completion_year": 2015,
        "date_of_birth": "1990-01-01",
        "birthplace": "Curitiba/PR",
        "nationality": "brasileira",
        "cpf": "07461638947",
    }
    mocks.notify.get_contact.return_value = {"phone": "42999999999", "email": "a@b.com"}
    mocks.notify.update_email.return_value = {}
    mocks.address.create_address.return_value = {}
    mocks.address.update_entity_cep.return_value = {}
    mocks.documents.update.return_value = {}
    mocks.documents.upload_image.return_value = {}
    mocks.documents.get.return_value = {
        "cnh": {"numero": "123", "foto_frente": "f", "foto_verso": "v"}
    }
    mocks.asaas.create_pixkey.return_value = {"holder_name": "Joao", "bank_name": "Banco"}
    mocks.ai.vision.return_value = "Uma pessoa sorrindo em uma selfie"
    mocks.roles.promote.return_value = {"roles": ["training"]}

    r = await client.post(
        "/api/v1/authenticated/captured",
        json={"name": "Joao Silva", "email": "a@b.com"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "personal"

    r = await client.post(
        "/api/v1/authenticated/personal",
        json={
            "gender": "M",
            "mother_name": "Maria",
            "father_name": "Jose",
            "marital_status": "solteiro",
        },
    )
    assert r.json()["status"] == "education"

    r = await client.post(
        "/api/v1/authenticated/educational",
        json={"education_level": "superior", "institution": "UFPR"},
    )
    assert r.json()["status"] == "birth"

    r = await client.post(
        "/api/v1/authenticated/birth",
        json={
            "date_of_birth": "1990-01-01",
            "birthplace": "Curitiba/PR",
            "nationality": "brasileira",
        },
    )
    assert r.json()["status"] == "address"

    r = await client.post(
        "/api/v1/authenticated/address",
        json={
            "cep": "80000000",
            "street": "Rua A",
            "number": "1",
            "neighborhood": "Centro",
            "city": "Curitiba",
            "state": "PR",
        },
    )
    assert r.json()["status"] == "documents"

    r = await client.post("/api/v1/authenticated/documents/submit")
    assert r.json()["status"] == "pixkey", r.text

    r = await client.post(
        "/api/v1/authenticated/pixkey",
        json={"key": "a@b.com", "key_type": "EMAIL"},
    )
    assert r.json()["status"] == "selfie", r.text

    r = await client.post(
        "/api/v1/authenticated/selfie",
        files={"file": ("selfie.jpg", b"fakebytes", "image/jpeg")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "completed"
    assert body["verified"] is True
    mocks.roles.promote.assert_awaited()

    async with async_session_maker() as session:
        candidate = await session.scalar(
            select(Candidate).where(Candidate.external_id == str(ext))
        )
    assert candidate.status == "completed"


async def test_documents_submit_incomplete_blocks(client, make_candidate, login_as, mocks):
    ext = await make_candidate(status="documents")
    login_as(ext)
    # nenhum documento completo -> submit deve recusar
    mocks.documents.get.return_value = {"rg": {"numero": None}, "cnh": {}}
    resp = await client.post("/api/v1/authenticated/documents/submit")
    assert resp.status_code == 422, resp.text


async def test_selfie_rejected_when_no_person(client, make_candidate, login_as, mocks):
    ext = await make_candidate(status="selfie")
    login_as(ext)
    mocks.documents.upload_image.return_value = {}
    mocks.ai.vision.return_value = "Uma paisagem com montanhas e um lago ao entardecer"

    resp = await client.post(
        "/api/v1/authenticated/selfie",
        files={"file": ("x.jpg", b"x", "image/jpeg")},
    )
    assert resp.status_code == 422, resp.text
    mocks.roles.promote.assert_not_awaited()


async def test_pixkey_uses_profile_cpf(client, make_candidate, login_as, mocks):
    ext = await make_candidate(status="pixkey")
    login_as(ext)
    mocks.profiles.get_one.return_value = {"cpf": "07461638947"}
    mocks.asaas.create_pixkey.return_value = {"holder_name": "Joao", "bank_name": "Banco"}

    resp = await client.post(
        "/api/v1/authenticated/pixkey",
        json={"key": "+5542999999999", "key_type": "PHONE"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "selfie"
    # o CPF passado ao asaas veio do perfil, nao do request
    _, kwargs = mocks.asaas.create_pixkey.await_args
    assert kwargs["document"] == "07461638947"
