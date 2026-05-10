from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from leads_bot.analyzer.analyzer import Analyzer
from leads_bot.db.models import Base, Lead, Source


@pytest.fixture
async def session(monkeypatch):
    for k, v in [
        ("TELEGRAM_API_ID", "1"), ("TELEGRAM_API_HASH", "x"),
        ("TELEGRAM_PHONE", "+1"), ("BOT_TOKEN", "x"),
        ("OWNER_TG_ID", "1"), ("ANTHROPIC_API_KEY", "x"),
    ]:
        monkeypatch.setenv(k, v)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def _make_lead(session, text):
    src = Source(
        tg_id=1, title="Design Jobs UA", type="channel",
        language="ru", region="ua", status="active",
    )
    session.add(src)
    await session.commit()
    lead = Lead(source_id=src.id, tg_message_id=1, raw_text=text, status="new")
    session.add(lead)
    await session.commit()
    return lead, src


async def test_ru_markers_hard_reject_skips_claude(session):
    claude = AsyncMock()
    claude.analyze = AsyncMock(side_effect=AssertionError("Claude must NOT be called"))
    analyzer = Analyzer(claude=claude)
    lead, src = await _make_lead(session, "Ищу дизайнера, оплата на Сбер")
    result = await analyzer.analyze_and_persist(session, lead, src.title, src.language)
    assert result.status == "filtered_out"
    assert result.client_country == "ru"


async def test_low_score_filtered_out(session):
    claude = AsyncMock()
    claude.analyze = AsyncMock(return_value={
        "is_lead": True, "project_type": "landing", "budget_usd": 500,
        "language": "ru", "client_country": "ua", "urgency": "low",
        "relevance_score": 40, "reasoning": "weak fit",
    })
    analyzer = Analyzer(claude=claude)
    lead, src = await _make_lead(session, "Ищу копирайтера или дизайнера")
    result = await analyzer.analyze_and_persist(session, lead, src.title, src.language)
    assert result.status == "filtered_out"
    assert result.relevance_score == 40


async def test_low_budget_filtered_out(session):
    claude = AsyncMock()
    claude.analyze = AsyncMock(return_value={
        "is_lead": True, "project_type": "landing", "budget_usd": 100,
        "language": "ru", "client_country": "ua", "urgency": "low",
        "relevance_score": 80, "reasoning": "tiny budget",
    })
    analyzer = Analyzer(claude=claude)
    lead, src = await _make_lead(session, "Ищу дизайнера на простой лендос")
    result = await analyzer.analyze_and_persist(session, lead, src.title, src.language)
    assert result.status == "filtered_out"


async def test_qualifying_lead_passes(session):
    claude = AsyncMock()
    claude.analyze = AsyncMock(return_value={
        "is_lead": True, "project_type": "design_system", "budget_usd": 1500,
        "language": "en", "client_country": "eu", "urgency": "med",
        "relevance_score": 88, "reasoning": "excellent match",
    })
    analyzer = Analyzer(claude=claude)
    lead, src = await _make_lead(session, "Looking for UI designer for SaaS")
    result = await analyzer.analyze_and_persist(session, lead, src.title, src.language)
    assert result.status == "drafted"
    assert result.relevance_score == 88
    assert result.budget_usd == 1500


async def test_claude_failure_marks_analysis_failed(session):
    claude = AsyncMock()
    claude.analyze = AsyncMock(side_effect=ValueError("bad json"))
    analyzer = Analyzer(claude=claude)
    lead, src = await _make_lead(session, "Looking for UI designer")
    result = await analyzer.analyze_and_persist(session, lead, src.title, src.language)
    assert result.status == "analysis_failed"
