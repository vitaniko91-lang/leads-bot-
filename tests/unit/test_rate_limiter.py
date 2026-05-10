from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from leads_bot.db.models import Base, RateLimit
from leads_bot.sender.rate_limiter import RateLimiter, RateLimitExceeded


@pytest.fixture
async def session(monkeypatch):
    for k, v in [
        ("TELEGRAM_API_ID", "1"), ("TELEGRAM_API_HASH", "x"),
        ("TELEGRAM_PHONE", "+1"), ("BOT_TOKEN", "x"),
        ("OWNER_TG_ID", "1"), ("ANTHROPIC_API_KEY", "x"),
        ("MAX_RESPONSES_PER_HOUR", "3"),
        ("MAX_RESPONSES_PER_DAY", "5"),
        ("MAX_RESPONSES_PER_WEEK", "10"),
    ]:
        monkeypatch.setenv(k, v)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def test_under_limit_passes(session):
    rl = RateLimiter()
    for _ in range(3):
        await rl.check_and_record(session)


async def test_over_hour_limit_raises(session):
    rl = RateLimiter()
    for _ in range(3):
        await rl.check_and_record(session)
    with pytest.raises(RateLimitExceeded) as exc:
        await rl.check_and_record(session)
    assert "hour" in str(exc.value)


async def test_old_records_dont_count(session):
    rl = RateLimiter()
    old = RateLimit(
        window="hour", window_start=datetime.utcnow() - timedelta(hours=2), sent_count=10
    )
    session.add(old)
    await session.commit()
    for _ in range(3):
        await rl.check_and_record(session)


async def test_random_delay_in_range(monkeypatch):
    for k, v in [
        ("TELEGRAM_API_ID", "1"), ("TELEGRAM_API_HASH", "x"),
        ("TELEGRAM_PHONE", "+1"), ("BOT_TOKEN", "x"),
        ("OWNER_TG_ID", "1"), ("ANTHROPIC_API_KEY", "x"),
        ("SEND_DELAY_MIN", "10"), ("SEND_DELAY_MAX", "20"),
    ]:
        monkeypatch.setenv(k, v)
    rl = RateLimiter()
    for _ in range(20):
        d = rl.random_delay_seconds()
        assert 10 <= d <= 20
