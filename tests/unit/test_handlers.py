from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from leads_bot.db.models import Base, Lead, Response, Source
from leads_bot.notifier.handlers import handle_callback


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


async def _setup(session):
    src = Source(
        tg_id=-100, title="x", type="channel",
        language="ru", region="ua", status="active",
    )
    session.add(src)
    await session.commit()
    lead = Lead(source_id=src.id, tg_message_id=1, raw_text="x", status="drafted")
    session.add(lead)
    await session.commit()
    resp = Response(lead_id=lead.id, draft_text="hi", status="drafted", sent_to="dm")
    session.add(resp)
    await session.commit()
    return src, lead, resp


async def test_approve_calls_sender(factory):
    async with factory() as s:
        src, lead, resp = await _setup(s)
        resp_id = resp.id

    sender = MagicMock()
    sender.send = AsyncMock()
    callback = MagicMock()
    callback.data = f"approve:{resp_id}"
    callback.answer = AsyncMock()

    await handle_callback(callback, factory, sender)

    sender.send.assert_awaited_once()
    callback.answer.assert_awaited()


async def test_skip_marks_skipped(factory):
    async with factory() as s:
        src, lead, resp = await _setup(s)
        resp_id = resp.id

    sender = MagicMock()
    sender.send = AsyncMock()
    callback = MagicMock()
    callback.data = f"skip:{resp_id}"
    callback.answer = AsyncMock()
    callback.message = MagicMock()
    callback.message.delete = AsyncMock()

    await handle_callback(callback, factory, sender)

    async with factory() as s:
        r = (await s.execute(select(Response).where(Response.id == resp_id))).scalar_one()
        assert r.status == "skipped"
    sender.send.assert_not_awaited()


async def test_mute_sets_muted_until(factory):
    async with factory() as s:
        src, lead, resp = await _setup(s)
        src_id = src.id

    sender = MagicMock()
    callback = MagicMock()
    callback.data = f"mute:{src_id}"
    callback.answer = AsyncMock()

    await handle_callback(callback, factory, sender)

    async with factory() as s:
        src2 = (await s.execute(select(Source).where(Source.id == src_id))).scalar_one()
        assert src2.muted_until is not None
        assert src2.muted_until > datetime.utcnow()
