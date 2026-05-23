"""Tests dos endpoints meta: /, /healthz, /docs, /openapi.json."""

from __future__ import annotations


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    j = r.json()
    assert j["app"] == "asaas-app"
    assert j["status"] == "up"


def test_root_redirects_to_docs(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"] == "/docs"


def test_root_follow_redirect(client):
    r = client.get("/", follow_redirects=True)
    assert r.status_code == 200
    assert "<title>" in r.text


def test_openapi_json(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    spec = r.json()
    assert spec["info"]["title"] == "asaas-app"
    paths = spec["paths"]
    # rotas criticas estao no schema
    for path in (
        "/api/v1/payment",
        "/api/v1/payment/qrcode",
        "/api/v1/pixkey",
        "/api/v1/config/status",
        "/webhook/",
    ):
        assert path in paths, f"{path} faltando no OpenAPI"


def test_openapi_payment_tem_400_responses(client):
    spec = client.get("/openapi.json").json()
    post_payment = spec["paths"]["/api/v1/payment"]["post"]
    assert "400" in post_payment["responses"]
    desc = post_payment["responses"]["400"]["description"]
    assert "pixkey_not_found" in desc
