"""Testes do CRUD multi-template e fallback automatico para default."""

from httpx import AsyncClient


async def test_list_templates_returns_seed_default(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/templates")
    assert resp.status_code == 200
    body = resp.json()
    slugs = {t["slug"] for t in body}
    assert "default" in slugs


async def test_get_default_template(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/templates/default")
    assert resp.status_code == 200
    body = resp.json()
    assert body["slug"] == "default"
    assert body["version"] >= 1
    assert body["is_active"] is True
    assert "{{title}}" in body["html"]


async def test_create_template_with_html(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/templates",
        json={
            "slug": "welcome",
            "name": "Boas-vindas",
            "html": "<p>Oi {{title}} - {{content}}</p>",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["slug"] == "welcome"
    assert body["version"] == 1
    assert body["is_active"] is True


async def test_create_template_duplicate_slug_conflict(client: AsyncClient) -> None:
    payload = {"slug": "checkout", "name": "Checkout", "html": "<p>{{content}}</p>"}
    await client.post("/api/v1/templates", json=payload)
    resp = await client.post("/api/v1/templates", json=payload)
    assert resp.status_code == 409


async def test_create_template_with_instruction_uses_ai(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/templates",
        json={
            "slug": "receipt",
            "name": "Recibo",
            "instruction": "Use paleta verde",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    # Mock da IA adiciona o marcador no fim
    assert "<!-- edited by AI -->" in body["html"]


async def test_create_template_rejects_both_html_and_instruction(
    client: AsyncClient,
) -> None:
    resp = await client.post(
        "/api/v1/templates",
        json={
            "slug": "ambos",
            "name": "Conflito",
            "html": "<p>x</p>",
            "instruction": "edita",
        },
    )
    assert resp.status_code == 400


async def test_create_template_rejects_when_neither_provided(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/templates",
        json={"slug": "vazio", "name": "Vazio"},
    )
    assert resp.status_code == 400


async def test_update_template_html_increments_version(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/templates",
        json={"slug": "v1", "name": "V1", "html": "<p>first</p>"},
    )
    resp = await client.put(
        "/api/v1/templates/v1", json={"html": "<p>second</p>"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"] == 2
    assert body["html"] == "<p>second</p>"


async def test_update_template_same_html_does_not_increment(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/templates",
        json={"slug": "static", "name": "Static", "html": "<p>same</p>"},
    )
    resp = await client.put(
        "/api/v1/templates/static", json={"html": "<p>same</p>"},
    )
    assert resp.status_code == 200
    assert resp.json()["version"] == 1


async def test_update_template_is_active_toggle(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/templates",
        json={"slug": "toggle", "name": "Toggle", "html": "<p>x</p>"},
    )
    resp = await client.put(
        "/api/v1/templates/toggle", json={"is_active": False},
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


async def test_delete_template_works(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/templates",
        json={"slug": "to-delete", "name": "Bye", "html": "<p>x</p>"},
    )
    resp = await client.delete("/api/v1/templates/to-delete")
    assert resp.status_code == 204

    follow = await client.get("/api/v1/templates/to-delete")
    # Fallback automatico para default — endpoint retorna 200 com o default
    assert follow.status_code == 200
    assert follow.json()["slug"] == "default"


async def test_delete_default_template_is_blocked(client: AsyncClient) -> None:
    resp = await client.delete("/api/v1/templates/default")
    assert resp.status_code == 400


async def test_get_unknown_slug_falls_back_to_default(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/templates/nao-existe")
    assert resp.status_code == 200
    assert resp.json()["slug"] == "default"


async def test_only_active_filter(client: AsyncClient) -> None:
    # Cria 2 templates, desativa um
    await client.post(
        "/api/v1/templates",
        json={"slug": "active-1", "name": "Ativo", "html": "<p>x</p>"},
    )
    await client.post(
        "/api/v1/templates",
        json={"slug": "inactive-1", "name": "Inativo", "html": "<p>x</p>"},
    )
    await client.put(
        "/api/v1/templates/inactive-1", json={"is_active": False},
    )

    resp = await client.get("/api/v1/templates?only_active=true")
    slugs = {t["slug"] for t in resp.json()}
    assert "active-1" in slugs
    assert "inactive-1" not in slugs
    assert "default" in slugs  # seed e' active
