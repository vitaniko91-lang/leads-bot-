from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from leads_bot.db.models import (
    Base,
    DiscoveryCandidate,
    Lead,
    Response,
    Source,
)
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


async def test_discover_add_creates_source(factory):
    async with factory() as s:
        s.add(DiscoveryCandidate(
            tg_id=-100, title="X", member_count=100,
            predicted_region="eu", language="en", status="pending",
        ))
        await s.commit()
        cand_id = (await s.execute(select(DiscoveryCandidate.id))).scalar_one()

    cb = MagicMock(); cb.data = f"discover_add:{cand_id}"
    cb.answer = AsyncMock(); cb.message = MagicMock()
    cb.message.edit_reply_markup = AsyncMock()

    await handle_callback(cb, factory, sender=MagicMock())

    async with factory() as s:
        src = (await s.execute(select(Source).where(Source.tg_id == -100))).scalar_one()
        assert src.status == "active"


async def test_discover_reject_marks_rejected(factory):
    async with factory() as s:
        s.add(DiscoveryCandidate(
            tg_id=-101, title="Y", status="pending",
            predicted_region="eu", language="en",
        ))
        await s.commit()
        cand_id = (await s.execute(select(DiscoveryCandidate.id))).scalar_one()

    cb = MagicMock(); cb.data = f"discover_reject:{cand_id}"
    cb.answer = AsyncMock(); cb.message = MagicMock()
    cb.message.edit_reply_markup = AsyncMock()

    await handle_callback(cb, factory, sender=MagicMock())

    async with factory() as s:
        c = await s.get(DiscoveryCandidate, cand_id)
        assert c.status == "rejected"


async def test_reply_in_dialog_sets_client_status(factory):
    async with factory() as s:
        src = Source(
            tg_id=-1, title="x", type="channel",
            language="ru", region="ua",
        )
        s.add(src); await s.commit()
        l = Lead(source_id=src.id, tg_message_id=1, raw_text="x", status="sent")
        s.add(l); await s.commit()
        r = Response(
            lead_id=l.id, draft_text="hi", status="sent",
            sent_at=datetime.utcnow(), client_replied=True,
        )
        s.add(r); await s.commit()
        rid = r.id

    cb = MagicMock(); cb.data = f"reply_in_dialog:{rid}"
    cb.answer = AsyncMock(); cb.message = MagicMock()
    cb.message.edit_reply_markup = AsyncMock()

    await handle_callback(cb, factory, sender=MagicMock())

    async with factory() as s:
        r = await s.get(Response, rid)
        assert r.client_status == "in_dialog"
