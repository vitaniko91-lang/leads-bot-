from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from leads_bot.db.models import Base, Lead, Response, Source, Template
from leads_bot.listener.client_reply_notifier import ClientReplyNotifier
from leads_bot.listener.dm_handler import process_incoming_dm


@pytest.fixture
async def factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def test_full_flow_marks_replied_and_messages_owner(factory):
    async with factory() as s:
        src = Source(tg_id=-1, title="x", type="channel", language="ru", region="ua")
        s.add(src); await s.commit()
        l = Lead(
            source_id=src.id, tg_message_id=1, raw_text="x",
            author_tg_id=777, author_username="bob",
            project_type="landing", client_country="eu",
            relevance_score=80, status="sent",
        )
        s.add(l); await s.commit()
        tpl = Template(
            name="A", variant="A", active=True, traffic_share=100, prompt="p",
        )
        s.add(tpl); await s.commit()
        r = Response(
            lead_id=l.id, template_id=tpl.id, author_tg_id_cached=777,
            draft_text="hi", status="sent",
            sent_at=datetime.utcnow() - timedelta(hours=1), sent_to="dm",
        )
        s.add(r); await s.commit()
        rid = r.id

    bot = MagicMock(); bot.send_message = AsyncMock()
    notifier = ClientReplyNotifier(bot=bot, owner_tg_id=999)

    await process_incoming_dm(
        factory, sender_id=777, dm_date_utc=datetime.utcnow(), notifier=notifier,
    )

    async with factory() as s:
        r = await s.get(Response, rid)
        assert r.client_replied is True

    bot.send_message.assert_awaited_once()
    args = bot.send_message.await_args
    assert args.args[0] == 999
    assert "#" in args.args[1]
    assert "@bob" in args.args[1]
    kb = args.kwargs["reply_markup"]
    flat = [b for row in kb.inline_keyboard for b in row]
    assert len(flat) == 3
