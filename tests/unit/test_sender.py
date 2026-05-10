from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from leads_bot.db.models import Base, Lead, Response, Source
from leads_bot.sender.rate_limiter import RateLimitExceeded
from leads_bot.sender.sender import Sender


@pytest.fixture
async def session(monkeypatch):
    for k, v in [
        ("TELEGRAM_API_ID", "1"), ("TELEGRAM_API_HASH", "x"),
        ("TELEGRAM_PHONE", "+1"), ("BOT_TOKEN", "x"),
        ("OWNER_TG_ID", "1"), ("ANTHROPIC_API_KEY", "x"),
        ("SEND_DELAY_MIN", "0"), ("SEND_DELAY_MAX", "0"),
    ]:
        monkeypatch.setenv(k, v)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def _setup(session, sent_to="dm"):
    src = Source(
        tg_id=-100, title="x", type="channel",
        language="ru", region="ua", status="active",
    )
    session.add(src)
    await session.commit()
    lead = Lead(
        source_id=src.id, tg_message_id=1, raw_text="x",
        author_tg_id=12345, author_username="ivanov",
        status="drafted",
    )
    session.add(lead)
    await session.commit()
    resp = Response(
        lead_id=lead.id, draft_text="hi", final_text="hi",
        status="approved", sent_to=sent_to,
    )
    session.add(resp)
    await session.commit()
    return src, lead, resp


def _fake_client_with_action():
    """Build a Telethon client mock with both .action() context manager and .send_message."""
    client = MagicMock()
    action_cm = MagicMock()
    action_cm.__aenter__ = AsyncMock(return_value=None)
    action_cm.__aexit__ = AsyncMock(return_value=None)
    client.action = MagicMock(return_value=action_cm)
    client.send_message = AsyncMock()
    return client


async def test_sender_sends_dm_via_telethon(session):
    src, lead, resp = await _setup(session, sent_to="dm")
    fake_telethon = _fake_client_with_action()

    sender = Sender(telethon_client=fake_telethon)
    await sender.send(session, resp.id)

    await session.refresh(resp)
    assert resp.status == "sent"
    assert resp.sent_at is not None
    fake_telethon.send_message.assert_awaited_once()


async def test_sender_skips_when_rate_limited(session, monkeypatch):
    monkeypatch.setenv("MAX_RESPONSES_PER_HOUR", "0")
    from leads_bot import config
    config._settings = None

    src, lead, resp = await _setup(session)
    fake_telethon = _fake_client_with_action()

    sender = Sender(telethon_client=fake_telethon)
    with pytest.raises(RateLimitExceeded):
        await sender.send(session, resp.id)
    fake_telethon.send_message.assert_not_awaited()


async def test_sender_increments_template_sent_count(session):
    from leads_bot.db.models import Template

    tpl = Template(name="x", variant="A", active=True, traffic_share=100, prompt="p")
    session.add(tpl); await session.commit()

    src, lead, resp = await _setup(session, sent_to="dm")
    resp.template_id = tpl.id
    await session.commit()

    fake_telethon = _fake_client_with_action()
    sender = Sender(telethon_client=fake_telethon)
    await sender.send(session, resp.id)

    await session.refresh(tpl)
    assert tpl.sent_count == 1


async def test_sender_marks_failed_on_user_blocked(session):
    from telethon.errors import UserIsBlockedError

    src, lead, resp = await _setup(session)
    fake_telethon = _fake_client_with_action()
    fake_telethon.send_message = AsyncMock(side_effect=UserIsBlockedError(request=None))

    sender = Sender(telethon_client=fake_telethon)
    await sender.send(session, resp.id)

    await session.refresh(resp)
    assert resp.status == "failed"
