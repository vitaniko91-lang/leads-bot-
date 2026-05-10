from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from leads_bot.db.models import Base, Lead, Response, Source, Template
from leads_bot.drafter.drafter import DraftResult
from leads_bot.db.session import ensure_bot_state
from leads_bot.pipeline import Pipeline
from leads_bot.templates.repo import TemplateRepo


@pytest.fixture
async def session(monkeypatch):
    for k, v in [
        ("TELEGRAM_API_ID", "1"), ("TELEGRAM_API_HASH", "x"),
        ("TELEGRAM_PHONE", "+1"), ("BOT_TOKEN", "x"),
        ("OWNER_TG_ID", "999"), ("ANTHROPIC_API_KEY", "x"),
        ("QUIET_HOURS_ENABLED", "false"),
    ]:
        monkeypatch.setenv(k, v)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    await ensure_bot_state(factory)
    async with factory() as s:
        yield s
    await engine.dispose()


async def test_pipeline_writes_template_id_and_author(session):
    src = Source(tg_id=-1, title="x", type="channel",
                 language="ru", region="ua", status="active")
    session.add(src); await session.commit()
    lead = Lead(
        source_id=src.id, tg_message_id=1,
        author_tg_id=42424242,
        raw_text="Looking for designer", status="new",
    )
    session.add(lead); await session.commit()

    tpl = Template(name="A", variant="A", active=True, traffic_share=100, prompt="sys")
    session.add(tpl); await session.commit()

    analyzer = MagicMock()

    async def _ana(s, l, ct, cl):
        l.is_lead = True; l.project_type = "landing"; l.budget_usd = 1000
        l.language = "en"; l.client_country = "eu"; l.urgency = "med"
        l.relevance_score = 80; l.status = "drafted"
        await s.commit(); return l

    analyzer.analyze_and_persist = AsyncMock(side_effect=_ana)

    drafter = MagicMock()
    drafter.draft = AsyncMock(return_value=DraftResult(text="Hi!", template_id=tpl.id))

    bot = MagicMock()
    bot.send_message = AsyncMock(return_value=MagicMock(message_id=1))

    repo = TemplateRepo(session)
    pipeline = Pipeline(
        analyzer=analyzer, drafter=drafter, bot=bot,
        owner_tg_id=999, templates=repo,
    )
    await pipeline.process_new_lead(session, lead, src)

    resp = (await session.execute(
        select(Response).where(Response.lead_id == lead.id)
    )).scalar_one()
    assert resp.template_id == tpl.id
    assert resp.author_tg_id_cached == 42424242
