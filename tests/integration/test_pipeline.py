from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from leads_bot.db.models import Base, Lead, Response, Source
from leads_bot.drafter.drafter import DraftResult
from leads_bot.pipeline import Pipeline


@pytest.fixture
async def session(monkeypatch):
    for k, v in [
        ("TELEGRAM_API_ID", "1"), ("TELEGRAM_API_HASH", "x"),
        ("TELEGRAM_PHONE", "+1"), ("BOT_TOKEN", "x"),
        ("OWNER_TG_ID", "999"), ("ANTHROPIC_API_KEY", "x"),
        # This suite verifies the immediate draft+notify path; quiet-hours
        # gating is covered separately in test_quiet_hours_flow.py. Disable
        # it here so the result is deterministic regardless of wall-clock time.
        ("QUIET_HOURS_ENABLED", "false"),
    ]:
        monkeypatch.setenv(k, v)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def test_qualifying_lead_creates_response_and_notifies(session):
    src = Source(
        tg_id=-100, title="Design Jobs UA", type="channel",
        language="ru", region="ua", status="active",
    )
    session.add(src)
    await session.commit()
    lead = Lead(
        source_id=src.id, tg_message_id=1,
        raw_text="Looking for UI designer for crypto landing, $1500",
        status="new",
    )
    session.add(lead)
    await session.commit()

    analyzer = MagicMock()

    async def _analyze(s, l, ct, cl):
        l.is_lead = True
        l.project_type = "landing"
        l.budget_usd = 1500
        l.language = "en"
        l.client_country = "eu"
        l.urgency = "med"
        l.relevance_score = 88
        l.reasoning = "good"
        l.status = "drafted"
        await s.commit()
        return l

    analyzer.analyze_and_persist = AsyncMock(side_effect=_analyze)

    drafter = MagicMock()
    drafter.draft = AsyncMock(
        return_value=DraftResult(text="Hi! Saw your post about a crypto landing...", template_id=None)
    )

    bot = MagicMock()
    bot.send_message = AsyncMock(return_value=MagicMock(message_id=42))

    pipeline = Pipeline(analyzer=analyzer, drafter=drafter, bot=bot, owner_tg_id=999)
    await pipeline.process_new_lead(session, lead, src)

    resp = (await session.execute(
        select(Response).where(Response.lead_id == lead.id)
    )).scalar_one()
    assert resp.draft_text.startswith("Hi!")
    assert resp.status == "drafted"

    bot.send_message.assert_awaited_once()
    call = bot.send_message.call_args
    assert call.args[0] == 999


async def test_filtered_out_lead_does_not_draft_or_notify(session):
    src = Source(
        tg_id=-100, title="x", type="channel",
        language="ru", region="ua", status="active",
    )
    session.add(src)
    await session.commit()
    lead = Lead(
        source_id=src.id, tg_message_id=1,
        raw_text="Ищу дизайнера, оплата на Сбер", status="new",
    )
    session.add(lead)
    await session.commit()

    analyzer = MagicMock()

    async def _analyze(s, l, ct, cl):
        l.status = "filtered_out"
        l.client_country = "ru"
        l.reasoning = "RU markers"
        await s.commit()
        return l

    analyzer.analyze_and_persist = AsyncMock(side_effect=_analyze)

    drafter = MagicMock()
    drafter.draft = AsyncMock()
    bot = MagicMock()
    bot.send_message = AsyncMock()

    pipeline = Pipeline(analyzer=analyzer, drafter=drafter, bot=bot, owner_tg_id=999)
    await pipeline.process_new_lead(session, lead, src)

    drafter.draft.assert_not_awaited()
    bot.send_message.assert_not_awaited()
