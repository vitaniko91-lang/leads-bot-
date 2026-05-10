from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from leads_bot.db.models import Base, BotState, Lead, Response, Source
from leads_bot.db.session import ensure_bot_state
from leads_bot.notifier.digest import (
    build_digest_text,
    collect_pending_digest_responses,
    run_morning_digest,
)


@pytest.fixture
async def factory(monkeypatch):
    for k, v in [
        ("TELEGRAM_API_ID", "1"), ("TELEGRAM_API_HASH", "x"),
        ("TELEGRAM_PHONE", "+1"), ("BOT_TOKEN", "x"),
        ("OWNER_TG_ID", "999"), ("ANTHROPIC_API_KEY", "x"),
    ]:
        monkeypatch.setenv(k, v)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    f = async_sessionmaker(engine, expire_on_commit=False)
    await ensure_bot_state(f)
    yield f
    await engine.dispose()


async def _seed(factory, n: int) -> list[int]:
    async with factory() as s:
        src = Source(tg_id=-100, title="x", type="channel",
                     language="ru", region="ua", status="active")
        s.add(src); await s.commit()
        ids = []
        for i in range(n):
            lead = Lead(source_id=src.id, tg_message_id=i + 1, raw_text="x",
                        project_type="landing", budget_usd=500 + i * 100,
                        relevance_score=70 + i, status="drafted")
            s.add(lead); await s.commit()
            resp = Response(lead_id=lead.id, draft_text="d",
                            status="pending_digest", sent_to="dm")
            s.add(resp); await s.commit()
            ids.append(resp.id)
        return ids


def test_build_digest_text_with_three_leads():
    rows = [
        MagicMock(id=145, lead=MagicMock(relevance_score=92, project_type="ui_ux", budget_usd=3000)),
        MagicMock(id=144, lead=MagicMock(relevance_score=78, project_type="landing", budget_usd=500)),
        MagicMock(id=143, lead=MagicMock(relevance_score=65, project_type="app", budget_usd=1200)),
    ]
    text = build_digest_text(rows)
    assert "3 лид" in text
    assert "#145" in text
    assert "92" in text
    assert "3000" in text


def test_build_digest_text_empty():
    text = build_digest_text([])
    assert "ничего" in text.lower() or "0" in text or "нет" in text.lower()


async def test_collect_pending_returns_only_pending_digest(factory):
    ids = await _seed(factory, 3)
    rows = await collect_pending_digest_responses(factory)
    assert len(rows) == 3
    assert {r.id for r in rows} == set(ids)


async def test_run_morning_digest_sends_and_promotes_to_drafted(factory):
    ids = await _seed(factory, 2)
    bot = MagicMock()
    bot.send_message = AsyncMock(return_value=MagicMock(message_id=1))

    await run_morning_digest(factory, bot=bot, owner_tg_id=999)

    bot.send_message.assert_awaited()
    async with factory() as s:
        rows = (await s.execute(select(Response).where(Response.id.in_(ids)))).scalars().all()
        for r in rows:
            assert r.status == "drafted"
        bs = (await s.execute(select(BotState).where(BotState.id == 1))).scalar_one()
        assert bs.last_digest_at is not None


async def test_run_morning_digest_no_op_when_empty(factory):
    bot = MagicMock(); bot.send_message = AsyncMock()
    await run_morning_digest(factory, bot=bot, owner_tg_id=999)
    bot.send_message.assert_awaited_once()
