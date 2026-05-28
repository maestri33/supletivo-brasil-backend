"""Testes E2E do fluxo de taxas (sqlite, asaas/notify stubbados).

Cobre: criação (2 payouts), guarda de duplicidade, correlação por payment_id no
webhook, derivação de status (FIRST_PAID/FULLY_PAID/FAILED), idempotência,
ping de onboarding e o gate de coordenador.
"""

from uuid import uuid4

from httpx import AsyncClient

FEES_URL = "/api/v1/authenticated/fees"
WEBHOOK_URL = "/api/v1/webhook/asaas-payout"


def _body(student: str | None = None) -> dict:
    return {
        "student_external_id": student or str(uuid4()),
        "description": "Taxa de matrícula 2026/1",
        "upfront": {"qrcode_payload": "0" * 30, "amount": 250.0},
        "scheduled": {
            "qrcode_payload": "1" * 30,
            "amount": 250.0,
            "date": "2026-07-01",
            "hour": 8,
        },
    }


def _pids(fee_json: dict) -> dict[str, str]:
    return {p["kind"]: p["payment_id"] for p in fee_json["payments"]}


async def _create(client: AsyncClient, student: str | None = None) -> dict:
    resp = await client.post(FEES_URL, json=_body(student))
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_create_dispatches_two_payouts(client: AsyncClient, fake_asaas) -> None:
    student = str(uuid4())
    fee = await _create(client, student)

    assert fee["status"] == "PENDING"
    assert fee["student_external_id"] == student
    kinds = {p["kind"]: p for p in fee["payments"]}
    assert set(kinds) == {"upfront", "scheduled"}
    assert kinds["upfront"]["status"] == "QUEUED"
    assert kinds["scheduled"]["status"] == "SCHEDULED"

    # asaas chamado com os payment_id determinísticos do fees
    assert [c[0] for c in fake_asaas.calls] == ["upfront", "scheduled"]
    assert fake_asaas.calls[0][1]["payment_id"] == kinds["upfront"]["payment_id"]
    assert fake_asaas.calls[1][1]["payment_id"] == kinds["scheduled"]["payment_id"]
    assert fake_asaas.calls[1][1]["date"] == "2026-07-01"


async def test_duplicate_active_fee_conflict(client: AsyncClient) -> None:
    student = str(uuid4())
    await _create(client, student)
    resp = await client.post(FEES_URL, json=_body(student))
    assert resp.status_code == 409
    assert resp.json()["code"] == "FEE_ALREADY_EXISTS"


async def test_webhook_upfront_paid_releases_access(client: AsyncClient, notifications) -> None:
    student = str(uuid4())
    fee = await _create(client, student)
    upfront_pid = _pids(fee)["upfront"]

    resp = await client.post(
        WEBHOOK_URL, json={"payment_id": upfront_pid, "kind": "qrcode", "status": "PAID"}
    )
    assert resp.status_code == 202
    assert resp.json()["fee_status"] == "FIRST_PAID"

    got = await client.get(f"{FEES_URL}/{fee['id']}")
    assert got.json()["status"] == "FIRST_PAID"
    assert ("access_released", student) in notifications


async def test_webhook_both_paid_fully_paid(client: AsyncClient, notifications) -> None:
    student = str(uuid4())
    fee = await _create(client, student)
    pids = _pids(fee)

    await client.post(WEBHOOK_URL, json={"payment_id": pids["upfront"], "status": "PAID"})
    resp = await client.post(WEBHOOK_URL, json={"payment_id": pids["scheduled"], "status": "PAID"})
    assert resp.json()["fee_status"] == "FULLY_PAID"

    assert ("access_released", student) in notifications
    assert ("fully_paid", student) in notifications


async def test_webhook_unknown_payment_ignored(client: AsyncClient) -> None:
    resp = await client.post(
        WEBHOOK_URL, json={"payment_id": "fee-ghost-upfront", "status": "PAID"}
    )
    assert resp.status_code == 202
    assert resp.json()["ignored"] is True


async def test_webhook_idempotent(client: AsyncClient, notifications) -> None:
    student = str(uuid4())
    fee = await _create(client, student)
    upfront_pid = _pids(fee)["upfront"]

    await client.post(WEBHOOK_URL, json={"payment_id": upfront_pid, "status": "PAID"})
    await client.post(WEBHOOK_URL, json={"payment_id": upfront_pid, "status": "PAID"})

    # status estável e notificação de acesso disparada uma única vez
    got = await client.get(f"{FEES_URL}/{fee['id']}")
    assert got.json()["status"] == "FIRST_PAID"
    assert notifications.count(("access_released", student)) == 1


async def test_webhook_onboarding_ping(client: AsyncClient) -> None:
    resp = await client.post(WEBHOOK_URL, json={"event": "ASAAS_APP_ONBOARDING"})
    assert resp.status_code == 202
    assert resp.json()["onboarding"] is True


async def test_webhook_payment_failed_notifies_coordinator(
    client: AsyncClient, notifications, coordinator_id
) -> None:
    fee = await _create(client)
    upfront_pid = _pids(fee)["upfront"]

    resp = await client.post(WEBHOOK_URL, json={"payment_id": upfront_pid, "status": "FAILED"})
    assert resp.json()["fee_status"] == "FAILED"
    assert ("payment_failed", str(coordinator_id), "upfront") in notifications


async def test_create_with_asaas_failure_marks_submit_error(
    client: AsyncClient, fake_asaas
) -> None:
    fake_asaas.raise_on = {"upfront"}
    fee = await _create(client)
    kinds = {p["kind"]: p for p in fee["payments"]}
    assert kinds["upfront"]["status"] == "SUBMIT_ERROR"
    assert kinds["upfront"]["last_error"]
    assert fee["status"] == "PENDING"


async def test_auth_required(client_noauth: AsyncClient) -> None:
    resp = await client_noauth.get(FEES_URL)
    # HTTPBearer recusa sem Authorization (401) ou role ausente (403).
    assert resp.status_code in (401, 403)
