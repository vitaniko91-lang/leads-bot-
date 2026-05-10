from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from leads_bot.db.models import Base, Lead, Response, Source, Template
from leads_bot.listener.dm_handler import process_incoming_dm


@pytest.fixture
async def factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def _setup(factory, *, sent_at, author_id=42, with_template=True):
    async with factory() as s:
        src = Source(tg_id=-1, title="x", type="channel", language="ru", region="ua")
        s.add(src); await s.commit()
        l = Lead(
            source_id=src.id, tg_message_id=1, raw_text="x",
            author_tg_id=author_id, status="sent",
        )
        s.add(l); await s.commit()
        tpl_id = None
        if with_template:
            tpl = Template(
                name="A", variant="A", active=True, traffic_share=100, prompt="p",
            )
            s.add(tpl); await s.commit()
            tpl_id = tpl.id
        r = Response(
            lead_id=l.id, template_id=tpl_id,
            author_tg_id_cached=author_id, draft_text="hi",
            status="sent", sent_at=sent_at, sent_to="dm",
        )
        s.add(r); await s.commit()
        return r.id, tpl_id


async def test_marks_client_replied_and_increments_template_counter(factory):
    sent_at = datetime.utcnow() - timedelta(hours=2)
    rid, tpl_id = await _setup(factory, sent_at=sent_at)

    notifier = AsyncMock()
    await process_incoming_dm(
        factory, sender_id=42, dm_date_utc=datetime.utcnow(),
        notifier=notifier,
    )

    async with factory() as s:
        r = await s.get(Response, rid)
        assert r.client_replied is True
        assert r.client_replied_at is not None
        tpl = await s.get(Template, tpl_id)
        assert tpl.reply_count == 1
    notifier.notify.assert_awaited_once()


async def test_skips_when_dm_predates_sent_at(factory):
    sent_at = datetime.utcnow()
    rid, _ = await _setup(factory, sent_at=sent_at)

    notifier = AsyncMock()
    await process_incoming_dm(
        factory, sender_id=42,
        dm_date_utc=sent_at - timedelta(minutes=5),
        notifier=notifier,
    )

    async with factory() as s:
        r = await s.get(Response, rid)
        assert r.client_replied is False
    notifier.notify.assert_not_awaited()


async def test_skips_when_response_older_than_7_days(factory):
    sent_at = datetime.utcnow() - timedelta(days=8)
    rid, _ = await _setup(factory, sent_at=sent_at)

    notifier = AsyncMock()
    await process_incoming_dm(
        factory, sender_id=42, dm_date_utc=datetime.utcnow(),
        notifier=notifier,
    )

    async with factory() as s:
        r = await s.get(Response, rid)
        assert r.client_replied is False
    notifier.notify.assert_not_awaited()


async def test_does_not_double_count_on_second_dm(factory):
    sent_at = datetime.utcnow() - timedelta(hours=2)
    rid, tpl_id = await _setup(factory, sent_at=sent_at)

    notifier = AsyncMock()
    for _ in range(3):
        await process_incoming_dm(
            factory, sender_id=42, dm_date_utc=datetime.utcnow(),
            notifier=notifier,
        )

    async with factory() as s:
        tpl = await s.get(Template, tpl_id)
        assert tpl.reply_count == 1
    assert notifier.notify.await_count == 1


async def test_no_response_for_sender_does_nothing(factory):
    notifier = AsyncMock()
    await process_incoming_dm(
        factory, sender_id=99999, dm_date_utc=datetime.utcnow(),
        notifier=notifier,
    )
    notifier.notify.assert_not_awaited()
