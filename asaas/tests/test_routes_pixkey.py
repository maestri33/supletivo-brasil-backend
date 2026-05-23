"""Tests HTTP do /api/v1/pixkey via AsyncClient — auth, schema, codigos de erro."""

from __future__ import annotations


def _mock_dict(fake_asaas, doc="12345678901"):
    fake_asaas.create_transfer.return_value = {
        "id": "tr_x",
        "bankAccount": {
            "cpfCnpj": doc,
            "ownerName": "TESTE",
            "bank": {"name": "INTER"},
        },
    }


async def test_post_pixkey_sucesso(client, seeded_apikey, fake_asaas):
    _mock_dict(fake_asaas)
    r = await client.post(
        "/api/v1/pixkey",
        json={
            "external_id": "ext1",
            "document": "12345678901",
            "key": "12345678901",
            "key_type": "CPF",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["external_id"] == "ext1"
    assert body["holder_name"] == "TESTE"
    assert body["validated_at"] is not None


async def test_post_pixkey_tipo_invalido(client, seeded_apikey):
    r = await client.post(
        "/api/v1/pixkey",
        json={
            "external_id": "x",
            "document": "12345678901",
            "key": "12345678901",
            "key_type": "TELEFONE",
        },
    )
    assert r.status_code == 400
    assert "invalid_key_type" in r.json()["detail"]


async def test_post_pixkey_dedup_external_id(client, seeded_apikey, fake_asaas):
    _mock_dict(fake_asaas)
    r1 = await client.post(
        "/api/v1/pixkey",
        json={
            "external_id": "ext1",
            "document": "12345678901",
            "key": "12345678901",
            "key_type": "CPF",
        },
    )
    assert r1.status_code == 200
    r2 = await client.post(
        "/api/v1/pixkey",
        json={
            "external_id": "ext1",
            "document": "98765432100",
            "key": "98765432100",
            "key_type": "CPF",
        },
    )
    assert r2.status_code == 400
    assert "external_id_already_exists" in r2.json()["detail"]


async def test_get_pixkey_404(client):
    r = await client.get("/api/v1/pixkey/no_existe")
    assert r.status_code == 404
    assert r.json()["detail"] == "not_found"


async def test_get_pixkey_lista_vazia(client):
    r = await client.get("/api/v1/pixkey")
    assert r.status_code == 200
    assert r.json() == []


async def test_delete_pixkey_404(client):
    r = await client.delete("/api/v1/pixkey/no_existe")
    assert r.status_code == 404


async def test_pixkey_lifecycle(client, seeded_apikey, fake_asaas):
    """add → list → get → delete → 404."""
    _mock_dict(fake_asaas)
    await client.post(
        "/api/v1/pixkey",
        json={
            "external_id": "x",
            "document": "12345678901",
            "key": "12345678901",
            "key_type": "CPF",
        },
    )
    assert len((await client.get("/api/v1/pixkey")).json()) == 1
    assert (await client.get("/api/v1/pixkey/x")).status_code == 200
    assert (await client.delete("/api/v1/pixkey/x")).json() == {"ok": True}
    assert (await client.get("/api/v1/pixkey/x")).status_code == 404


async def test_pixkey_check_via_route(client, seeded_apikey, fake_asaas):
    _mock_dict(fake_asaas, doc="55555555555")
    r = await client.get("/api/v1/pixkey/check/55555555555")
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "dict"
    assert body["data"]["holder_name"] == "TESTE"


async def test_pixkey_request_validation_422(client):
    """Pydantic rejeita body invalido como 422."""
    r = await client.post("/api/v1/pixkey", json={"external_id": ""})  # falta campos
    assert r.status_code == 422
