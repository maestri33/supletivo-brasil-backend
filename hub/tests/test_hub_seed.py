"""Seed do polo default — valida o INSERT idempotente usado pela migração 0001."""

from sqlalchemy import text

from app.seed import (
    DEFAULT_HUB_BRAND,
    DEFAULT_HUB_ID,
    DEFAULT_HUB_NAME,
    default_hub_insert_sql,
)


async def test_seed_creates_single_default_hub(session_factory) -> None:
    async with session_factory() as session:
        await session.execute(text(default_hub_insert_sql("hub")))
        await session.commit()
        rows = (await session.execute(text("SELECT id, name, brand FROM hub.hub"))).all()

    assert len(rows) == 1
    row = rows[0]
    assert str(row.id) == DEFAULT_HUB_ID
    assert row.name == DEFAULT_HUB_NAME
    assert row.brand == DEFAULT_HUB_BRAND


async def test_seed_is_idempotent(session_factory) -> None:
    sql = text(default_hub_insert_sql("hub"))
    async with session_factory() as session:
        await session.execute(sql)
        await session.execute(sql)
        await session.commit()
        count = (await session.execute(text("SELECT count(*) FROM hub.hub"))).scalar_one()

    assert count == 1
