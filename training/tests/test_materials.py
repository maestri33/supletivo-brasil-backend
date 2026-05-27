"""Testes de autoria de materia: CRUD + upload/download de midia."""

from uuid import uuid4

BASE = "/api/v1/demilitarized/materials"


async def test_create_and_get(client):
    payload = {
        "title": "Boas-vindas",
        "text_content": "Bem-vindo ao treinamento.",
        "question": "Qual o objetivo?",
        "expected_answer": "Virar promotor.",
    }
    resp = await client.post(BASE, json=payload)
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Boas-vindas"
    assert body["has_video"] is False
    assert body["has_photo"] is False
    mid = body["id"]

    resp = await client.get(f"{BASE}/{mid}")
    assert resp.status_code == 200
    assert resp.json()["question"] == "Qual o objetivo?"


async def test_create_rejects_blank_title(client):
    payload = {"title": "", "text_content": "x", "question": "q", "expected_answer": "r"}
    resp = await client.post(BASE, json=payload)
    assert resp.status_code == 422


async def test_list(client, make_material):
    await make_material(title="A")
    await make_material(title="B")
    resp = await client.get(BASE)
    assert resp.status_code == 200
    assert resp.json()["total"] == 2


async def test_get_unknown_returns_404(client):
    resp = await client.get(f"{BASE}/{uuid4()}")
    assert resp.status_code == 404


async def test_update(client, make_material):
    mid = await make_material()
    resp = await client.put(f"{BASE}/{mid}", json={"title": "Atualizado"})
    assert resp.status_code == 200
    assert resp.json()["title"] == "Atualizado"


async def test_upload_and_download_video(client, make_material):
    mid = await make_material()
    resp = await client.post(
        f"{BASE}/{mid}/video",
        files={"file": ("aula.mp4", b"\x00\x01videodata", "video/mp4")},
    )
    assert resp.status_code == 200
    assert resp.json()["has_video"] is True

    resp = await client.get(f"{BASE}/{mid}/video")
    assert resp.status_code == 200
    assert resp.content == b"\x00\x01videodata"


async def test_upload_photo_wrong_mime_rejected(client, make_material):
    mid = await make_material()
    resp = await client.post(
        f"{BASE}/{mid}/photo",
        files={"file": ("nope.mp4", b"data", "video/mp4")},
    )
    assert resp.status_code == 422


async def test_download_missing_video_returns_404(client, make_material):
    mid = await make_material()
    resp = await client.get(f"{BASE}/{mid}/video")
    assert resp.status_code == 404
