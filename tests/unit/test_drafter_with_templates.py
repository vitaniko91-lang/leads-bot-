import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from leads_bot.db.models import Base, Template
from leads_bot.drafter.drafter import Drafter, DraftResult
from leads_bot.drafter.profile import load_profile
from leads_bot.templates.repo import TemplateRepo


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


@pytest.fixture
def profile(tmp_path):
    p = tmp_path / "profile.json"
    p.write_text(json.dumps({
        "name": "Vitalina", "portfolio_url": "https://x.design",
        "telegram": "@v", "min_rate_usd_per_hour": 50,
        "tone": "friendly", "payment_methods": ["wise"],
        "cases": [{"title": "Crypto", "tags": ["landing"], "description": "x", "url": "u"}],
    }))
    return load_profile(p)


async def _seed_templates(session, *defs):
    for kw in defs:
        kw.setdefault("variant", "A"); kw.setdefault("active", True)
        kw.setdefault("traffic_share", 100); kw.setdefault("prompt", "TPL prompt")
        session.add(Template(**kw))
    await session.commit()


async def test_drafter_uses_template_prompt_as_system(profile, session):
    await _seed_templates(session,
        {"name": "Friendly", "prompt": "FRIENDLY_SYSTEM_PROMPT", "traffic_share": 100})
    repo = TemplateRepo(session)

    fake_client = MagicMock()
    fake_msg = MagicMock()
    fake_msg.content = [MagicMock(text="Hi!")]
    fake_client.messages.create = AsyncMock(return_value=fake_msg)

    drafter = Drafter(profile, repo, client=fake_client)
    result = await drafter.draft("Looking for UI designer", "landing", "en")

    assert isinstance(result, DraftResult)
    assert result.text == "Hi!"
    assert result.template_id is not None

    call = fake_client.messages.create.call_args.kwargs
    assert call["system"] == "FRIENDLY_SYSTEM_PROMPT"


async def test_drafter_falls_back_when_no_active_templates(profile, session):
    repo = TemplateRepo(session)

    fake_client = MagicMock()
    fake_msg = MagicMock(); fake_msg.content = [MagicMock(text="Hi!")]
    fake_client.messages.create = AsyncMock(return_value=fake_msg)

    drafter = Drafter(profile, repo, client=fake_client)
    result = await drafter.draft("Looking for UI designer", "landing", "en")

    assert result.text == "Hi!"
    assert result.template_id is None

    from leads_bot.drafter.prompts import DRAFTER_SYSTEM
    assert fake_client.messages.create.call_args.kwargs["system"] == DRAFTER_SYSTEM


async def test_drafter_passes_user_prompt_with_lead_text(profile, session):
    await _seed_templates(session, {"name": "X", "prompt": "sys"})
    repo = TemplateRepo(session)

    fake_client = MagicMock()
    fake_msg = MagicMock(); fake_msg.content = [MagicMock(text="ok")]
    fake_client.messages.create = AsyncMock(return_value=fake_msg)

    drafter = Drafter(profile, repo, client=fake_client)
    await drafter.draft("Looking for UI designer for crypto landing", "landing", "en")

    user_content = fake_client.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "Looking for UI designer for crypto landing" in user_content
    assert "Crypto" in user_content
