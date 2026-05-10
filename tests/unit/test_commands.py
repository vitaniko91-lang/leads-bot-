from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from leads_bot.db.models import Base, BotState, Lead, Response, Source
from leads_bot.db.session import ensure_bot_state
from leads_bot.notifier.commands import (
    cmd_draft_retry,
    cmd_pause,
    cmd_profile,
    cmd_quiet,
    cmd_resume,
    cmd_sources,
    cmd_sources_add,
    cmd_sources_pause,
    cmd_stats,
    cmd_templates,
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
    await ensure_bot_state(f)
    yield f
    await engine.dispose()


@pytest.fixture(autouse=True)
def _patch_get_peer_id(monkeypatch):
    """Stub Telethon get_peer_id for sources_add tests."""
    from leads_bot.sources import service
    monkeypatch.setattr(service, "get_peer_id", lambda e: e._tg_id)


def _msg(text: str):
    m = MagicMock()
    m.text = text
    m.answer = AsyncMock()
    return m


async def test_stats_with_empty_db(factory):
    msg = _msg("/stats")
    await cmd_stats(msg, factory)
    msg.answer.assert_awaited_once()
    out = msg.answer.call_args.args[0]
    assert "0" in out
    assert "лидов" in out.lower()


async def test_stats_counts_today(factory):
    async with factory() as s:
        src = Source(tg_id=-100, title="x", type="channel",
                     language="ru", region="ua", status="active")
        s.add(src); await s.commit()
        s.add(Lead(source_id=src.id, tg_message_id=1, raw_text="x", status="drafted"))
        s.add(Lead(source_id=src.id, tg_message_id=2, raw_text="x", status="filtered_out"))
        s.add(Lead(source_id=src.id, tg_message_id=3, raw_text="x", status="sent"))
        await s.commit()
        lead = (await s.execute(select(Lead).limit(1))).scalar_one()
        s.add(Response(lead_id=lead.id, draft_text="x", final_text="x",
                       status="sent", sent_at=datetime.utcnow()))
        await s.commit()

    msg = _msg("/stats")
    await cmd_stats(msg, factory)
    out = msg.answer.call_args.args[0]
    assert "3" in out
    assert "1" in out


async def test_sources_lists_all(factory):
    async with factory() as s:
        s.add(Source(tg_id=-100, title="Design Jobs UA", type="channel",
                     language="uk", region="ua", status="active"))
        s.add(Source(tg_id=-101, title="UX Berlin", type="channel",
                     language="en", region="eu", status="paused"))
        await s.commit()

    msg = _msg("/sources")
    await cmd_sources(msg, factory)
    out = msg.answer.call_args.args[0]
    assert "Design Jobs UA" in out
    assert "UX Berlin" in out
    assert "active" in out
    assert "paused" in out


async def test_sources_add_calls_service(factory):
    msg = _msg("/sources add @design_jobs_ua ua uk")
    fake_client = MagicMock()
    entity = MagicMock()
    entity._tg_id = -1001234567890
    entity.title = "Design Jobs UA"
    entity.megagroup = False
    fake_client.get_entity = AsyncMock(return_value=entity)

    await cmd_sources_add(msg, factory, fake_client)
    out = msg.answer.call_args.args[0]
    assert "Design Jobs UA" in out or "added" in out.lower()


async def test_sources_add_bad_args(factory):
    msg = _msg("/sources add only_one_arg")
    fake_client = MagicMock()
    await cmd_sources_add(msg, factory, fake_client)
    out = msg.answer.call_args.args[0]
    assert "usage" in out.lower() or "формат" in out.lower()


async def test_sources_pause_changes_status(factory):
    async with factory() as s:
        src = Source(tg_id=-100, title="x", type="channel",
                     language="ru", region="ua", status="active")
        s.add(src); await s.commit()
        sid = src.id

    msg = _msg(f"/sources pause {sid}")
    await cmd_sources_pause(msg, factory)
    async with factory() as s:
        row = (await s.execute(select(Source).where(Source.id == sid))).scalar_one()
        assert row.status == "paused"


async def test_pause_resume_toggle_botstate(factory):
    msg_p = _msg("/pause")
    await cmd_pause(msg_p, factory)
    async with factory() as s:
        bs = (await s.execute(select(BotState).where(BotState.id == 1))).scalar_one()
        assert bs.paused is True

    msg_r = _msg("/resume")
    await cmd_resume(msg_r, factory)
    async with factory() as s:
        bs = (await s.execute(select(BotState).where(BotState.id == 1))).scalar_one()
        assert bs.paused is False


async def test_quiet_command_updates_runtime_settings(factory):
    msg = _msg("/quiet 22:00-09:00")
    await cmd_quiet(msg, factory)
    out = msg.answer.call_args.args[0]
    assert "22:00-09:00" in out
    async with factory() as s:
        bs = (await s.execute(select(BotState).where(BotState.id == 1))).scalar_one()
        assert bs.quiet_hours_override == "22:00-09:00"


async def test_profile_shows_loaded_profile(tmp_path, factory):
    import json
    p = tmp_path / "profile.json"
    p.write_text(json.dumps({
        "name": "Vitalina", "portfolio_url": "https://x.design",
        "telegram": "@v", "min_rate_usd_per_hour": 60, "tone": "friendly",
        "payment_methods": ["wise"],
        "cases": [{"title": "C", "tags": ["landing"], "description": "d", "url": "u"}],
    }))
    msg = _msg("/profile")
    await cmd_profile(msg, factory, profile_path=p)
    out = msg.answer.call_args.args[0]
    assert "Vitalina" in out
    assert "60" in out


async def test_templates_stub_replies(factory):
    msg = _msg("/templates")
    await cmd_templates(msg, factory)
    out = msg.answer.call_args.args[0]
    assert "iter" in out.lower() or "итер" in out.lower()


async def test_draft_retry_calls_pipeline(factory):
    async with factory() as s:
        src = Source(tg_id=-100, title="x", type="channel",
                     language="ru", region="ua", status="active")
        s.add(src); await s.commit()
        lead = Lead(source_id=src.id, tg_message_id=1, raw_text="hi",
                    project_type="landing", language="en",
                    relevance_score=80, status="drafted")
        s.add(lead); await s.commit()
        lid = lead.id

    msg = _msg(f"/draft {lid} retry")
    pipeline = MagicMock()
    pipeline.regenerate_draft = AsyncMock()
    await cmd_draft_retry(msg, factory, pipeline)
    pipeline.regenerate_draft.assert_awaited_once()
