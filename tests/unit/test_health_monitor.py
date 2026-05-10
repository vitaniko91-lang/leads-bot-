from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from leads_bot.db.models import Base, BotState
from leads_bot.db.session import ensure_bot_state
from leads_bot.health.monitor import HealthMonitor


@pytest.fixture
async def factory(monkeypatch):
    for k, v in [
        ("TELEGRAM_API_ID", "1"), ("TELEGRAM_API_HASH", "x"),
        ("TELEGRAM_PHONE", "+1"), ("BOT_TOKEN", "x"),
        ("OWNER_TG_ID", "999"), ("ANTHROPIC_API_KEY", "x"),
        ("HEALTHCHECK_FAILURE_THRESHOLD", "3"),
    ]:
        monkeypatch.setenv(k, v)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    f = async_sessionmaker(engine, expire_on_commit=False)
    await ensure_bot_state(f)
    yield f
    await engine.dispose()


async def test_success_resets_counter(factory):
    user_client = MagicMock()
    user_client.get_me = AsyncMock(return_value=MagicMock(id=1))
    bot = MagicMock(); bot.send_message = AsyncMock()
    monitor = HealthMonitor(user_client, bot, owner_tg_id=999, factory=factory)

    async with factory() as s:
        bs = (await s.execute(select(BotState).where(BotState.id == 1))).scalar_one()
        bs.consecutive_health_fails = 2
        await s.commit()

    await monitor.check_once()

    async with factory() as s:
        bs = (await s.execute(select(BotState).where(BotState.id == 1))).scalar_one()
        assert bs.consecutive_health_fails == 0
        assert bs.last_health_ok_at is not None
    bot.send_message.assert_not_awaited()


async def test_failure_increments_counter(factory):
    user_client = MagicMock()
    user_client.get_me = AsyncMock(side_effect=ConnectionError("boom"))
    bot = MagicMock(); bot.send_message = AsyncMock()
    monitor = HealthMonitor(user_client, bot, owner_tg_id=999, factory=factory)

    await monitor.check_once()
    async with factory() as s:
        bs = (await s.execute(select(BotState).where(BotState.id == 1))).scalar_one()
        assert bs.consecutive_health_fails == 1
    bot.send_message.assert_not_awaited()


async def test_threshold_reached_alerts_owner_and_resets(factory):
    user_client = MagicMock()
    user_client.get_me = AsyncMock(side_effect=ConnectionError("boom"))
    bot = MagicMock(); bot.send_message = AsyncMock()
    monitor = HealthMonitor(user_client, bot, owner_tg_id=999, factory=factory)

    for _ in range(3):
        await monitor.check_once()

    bot.send_message.assert_awaited_once()
    msg = bot.send_message.call_args.args[1]
    assert "health" in msg.lower() or "связь" in msg.lower()
    async with factory() as s:
        bs = (await s.execute(select(BotState).where(BotState.id == 1))).scalar_one()
        assert bs.consecutive_health_fails == 0


async def test_alert_send_failure_does_not_crash(factory):
    user_client = MagicMock()
    user_client.get_me = AsyncMock(side_effect=ConnectionError("boom"))
    bot = MagicMock()
    bot.send_message = AsyncMock(side_effect=RuntimeError("bot down too"))
    monitor = HealthMonitor(user_client, bot, owner_tg_id=999, factory=factory)
    for _ in range(3):
        await monitor.check_once()
