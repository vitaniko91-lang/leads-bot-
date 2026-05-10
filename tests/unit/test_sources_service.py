from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from leads_bot.db.models import Base, Source
from leads_bot.sources.service import (
    InvalidRegion,
    SourceAlreadyExists,
    SourceNotFound,
    add_source_from_link,
    list_sources,
    pause_source,
    resume_source,
)


@pytest.fixture
async def factory(monkeypatch):
    for k, v in [
        ("TELEGRAM_API_ID", "1"), ("TELEGRAM_API_HASH", "x"),
        ("TELEGRAM_PHONE", "+1"), ("BOT_TOKEN", "x"),
        ("OWNER_TG_ID", "1"), ("ANTHROPIC_API_KEY", "x"),
    ]:
        monkeypatch.setenv(k, v)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    f = async_sessionmaker(engine, expire_on_commit=False)
    yield f
    await engine.dispose()


def _fake_client(tg_id: int, title: str, megagroup: bool = False):
    """Return a MagicMock that mimics Telethon get_entity returning a Channel."""
    entity = MagicMock()
    entity._tg_id = tg_id  # used by patched get_peer_id below
    entity.title = title
    entity.megagroup = megagroup
    entity.broadcast = not megagroup
    client = MagicMock()
    client.get_entity = AsyncMock(return_value=entity)
    return client, entity


@pytest.fixture(autouse=True)
def _patch_get_peer_id(monkeypatch):
    """Stub Telethon's get_peer_id since real impl rejects MagicMock entities."""
    from leads_bot.sources import service
    monkeypatch.setattr(service, "get_peer_id", lambda e: e._tg_id)


async def test_list_sources_empty(factory):
    rows = await list_sources(factory)
    assert rows == []


async def test_add_source_from_username(factory):
    client, _ = _fake_client(-1001234567890, "Design Jobs UA")
    src = await add_source_from_link(
        factory, client=client, link="@design_jobs_ua",
        region="ua", language="uk",
    )
    assert src.title == "Design Jobs UA"
    assert src.region == "ua"
    assert src.status == "active"
    client.get_entity.assert_awaited_once_with("design_jobs_ua")


async def test_add_source_from_t_me_link(factory):
    client, _ = _fake_client(-1001234567890, "X")
    await add_source_from_link(
        factory, client=client, link="https://t.me/design_jobs_ua",
        region="eu", language="en",
    )
    client.get_entity.assert_awaited_once_with("design_jobs_ua")


async def test_add_source_rejects_ru_region(factory):
    client, _ = _fake_client(-100, "X")
    with pytest.raises(InvalidRegion):
        await add_source_from_link(
            factory, client=client, link="@x_test", region="ru", language="ru",
        )


async def test_add_source_dedup(factory):
    client, _ = _fake_client(-1001234567890, "X")
    await add_source_from_link(
        factory, client=client, link="@x_test", region="ua", language="uk"
    )
    with pytest.raises(SourceAlreadyExists):
        await add_source_from_link(
            factory, client=client, link="@x_test", region="ua", language="uk"
        )


async def test_pause_and_resume(factory):
    client, _ = _fake_client(-1001234567890, "X")
    src = await add_source_from_link(
        factory, client=client, link="@x_test", region="ua", language="uk"
    )
    await pause_source(factory, src.id)
    async with factory() as s:
        row = (await s.execute(select(Source).where(Source.id == src.id))).scalar_one()
        assert row.status == "paused"
    await resume_source(factory, src.id)
    async with factory() as s:
        row = (await s.execute(select(Source).where(Source.id == src.id))).scalar_one()
        assert row.status == "active"


async def test_pause_missing_raises(factory):
    with pytest.raises(SourceNotFound):
        await pause_source(factory, 999)
