from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from leads_bot.db.models import Base, Lead, Response, Source
from leads_bot.db.session import ensure_bot_state
from leads_bot.notifier.digest import run_morning_digest
from leads_bot.pipeline import Pipeline


@pytest.fixture
async def session_and_factory(monkeypatch):
    for k, v in [
        ("TELEGRAM_API_ID", "1"), ("TELEGRAM_API_HASH", "x"),
        ("TELEGRAM_PHONE", "+1"), ("BOT_TOKEN", "x"),
        ("OWNER_TG_ID", "999"), ("ANTHROPIC_API_KEY", "x"),
        ("QUIET_HOURS", "23:00-08:00"), ("QUIET_HOURS_ENABLED", "true"),
        ("TIMEZONE", "UTC"),
    ]:
        monkeypatch.setenv(k, v)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    f = async_sessionmaker(engine, expire_on_commit=False)
    await ensure_bot_state(f)
    async with f() as s:
        yield s, f
    await engine.dispose()


async def test_during_quiet_no_card_response_marked_pending(session_and_factory):
    session, factory = session_and_factory
    src = Source(tg_id=-100, title="x", type="channel",
                 language="ru", region="ua", status="active")
    session.add(src); await session.commit()
    lead = Lead(source_id=src.id, tg_message_id=1,
                raw_text="Looking for designer", status="new")
    session.add(lead); await session.commit()

    analyzer = MagicMock()

    async def _analyze(s, l, ct, cl):
        l.is_lead = True; l.project_type = "landing"; l.budget_usd = 1000
        l.language = "en"; l.client_country = "eu"; l.urgency = "med"
        l.relevance_score = 88; l.reasoning = "ok"; l.status = "drafted"
        await s.commit(); return l

    analyzer.analyze_and_persist = AsyncMock(side_effect=_analyze)
    drafter = MagicMock(); drafter.draft = AsyncMock(return_value="hi")
    bot = MagicMock(); bot.send_message = AsyncMock()

    pipeline = Pipeline(
        analyzer=analyzer, drafter=drafter, bot=bot,
        owner_tg_id=999, factory=factory,
    )

    fixed_now = datetime(2026, 5, 17, 2, 0, tzinfo=ZoneInfo("UTC"))
    with patch("leads_bot.pipeline._utcnow_aware", return_value=fixed_now):
        await pipeline.process_new_lead(session, lead, src)

    bot.send_message.assert_not_awaited()
    resp = (await session.execute(
        select(Response).where(Response.lead_id == lead.id)
    )).scalar_one()
    assert resp.status == "pending_digest"


async def test_morning_digest_after_quiet_releases_pending(session_and_factory):
    session, factory = session_and_factory
    src = Source(tg_id=-100, title="x", type="channel",
                 language="ru", region="ua", status="active")
    session.add(src); await session.commit()
    lead = Lead(source_id=src.id, tg_message_id=1, raw_text="x",
                project_type="landing", budget_usd=1500, relevance_score=88,
                status="drafted")
    session.add(lead); await session.commit()
    resp = Response(lead_id=lead.id, draft_text="d",
                    status="pending_digest", sent_to="dm")
    session.add(resp); await session.commit()

    bot = MagicMock(); bot.send_message = AsyncMock(return_value=MagicMock(message_id=1))
    await run_morning_digest(factory, bot=bot, owner_tg_id=999)

    await session.refresh(resp)
    assert resp.status == "drafted"
    bot.send_message.assert_awaited()
