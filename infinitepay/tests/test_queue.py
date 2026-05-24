from app.db import async_session_maker
from app.models.models import OutboundJob
from app.workers import outbound_queue as q


async def test_process_due_marks_delivered(db, monkeypatch):
    jid = await q.enqueue(db, url="https://backend.test/hook/", payload={"x": 1})
    await db.commit()

    calls: list = []

    async def fake_deliver(url, payload):
        calls.append((url, payload))
        return True, None, 200

    monkeypatch.setattr(q, "_deliver_payload", fake_deliver)

    assert await q.process_due() == 1
    assert calls == [("https://backend.test/hook/", {"x": 1})]

    async with async_session_maker() as s:
        job = await s.get(OutboundJob, jid)
        assert job.attempts == 1
        assert job.delivered_at is not None
        assert job.last_error is None


async def test_process_due_retries_on_failure(db, monkeypatch):
    jid = await q.enqueue(db, url="https://backend.test/hook/", payload={"x": 1})
    await db.commit()

    async def fake_deliver(url, payload):
        return False, "boom", 500

    monkeypatch.setattr(q, "_deliver_payload", fake_deliver)

    assert await q.process_due() == 1

    async with async_session_maker() as s:
        job = await s.get(OutboundJob, jid)
        assert job.delivered_at is None
        assert job.attempts == 1
        assert job.last_error == "boom"
