"""Testes do endpoint POST /api/v1/messages/test-email.

SMTPClient e' mockado no conftest (`_isolate_external_io`). Aqui validamos
o fluxo: render com template selecionado + persistencia de Log.
"""

from httpx import AsyncClient


async def test_test_email_with_default_template(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/messages/test-email",
        json={"to_email": "test-xxx@srv1.mail-tester.com"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["sent"] is True
    assert body["to_email"] == "test-xxx@srv1.mail-tester.com"
    assert body["template_slug"] == "default"
    assert body["template_version"] >= 1
    # SMTPClient.send_email retorna {to, subject, from, refused}
    assert body["smtp_response"]["refused"] == {}
    assert body["smtp_response"]["to"] == "test-xxx@srv1.mail-tester.com"


async def test_test_email_with_custom_slug(client: AsyncClient) -> None:
    # Cria template custom
    await client.post(
        "/api/v1/templates",
        json={"slug": "diag", "name": "Diagnostico", "html": "<p>{{content}}</p>"},
    )

    resp = await client.post(
        "/api/v1/messages/test-email",
        json={
            "to_email": "ops@example.com",
            "title": "Smoke",
            "content": "Teste smoke",
            "template_slug": "diag",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["sent"] is True
    assert body["template_slug"] == "diag"


async def test_test_email_unknown_slug_falls_back_to_default(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/messages/test-email",
        json={
            "to_email": "fallback@example.com",
            "template_slug": "nao-existe-1234",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["template_slug"] == "default"


async def test_test_email_persists_audit_log(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/messages/test-email",
        json={"to_email": "audit@example.com"},
    )

    logs = await client.get("/api/v1/logs?limit=5")
    actions = {row["action"] for row in logs.json()}
    assert "email.test_sent" in actions
