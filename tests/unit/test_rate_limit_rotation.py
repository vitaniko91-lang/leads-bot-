from datetime import datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from leads_bot.db.models import Base, RateLimit
from leads_bot.sender.rate_limiter import RateLimiter


@pytest.fixture
async def session(monkeypatch):
    for k, v in [
        ("TELEGRAM_API_ID", "1"), ("TELEGRAM_API_HASH", "x"),
        ("TELEGRAM_PHONE", "+1"), ("BOT_TOKEN", "x"),
        ("OWNER_TG_ID", "1"), ("ANTHROPIC_API_KEY", "x"),
        ("RATE_LIMIT_RETENTION_HOURS", "168"),
    ]:
        monkeypatch.setenv(k, v)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    f = async_sessionmaker(engine, expire_on_commit=False)
    async with f() as s:
        yield s
    await engine.dispose()


async def test_rotate_drops_old_records(session):
    now = datetime.utcnow()
    for d in [200, 180, 170, 169, 200]:
        session.add(RateLimit(window="hour", window_start=now - timedelta(hours=d), sent_count=1))
    for d in [10, 50, 167]:
        session.add(RateLimit(window="hour", window_start=now - timedelta(hours=d), sent_count=1))
    await session.commit()

    rl = RateLimiter()
    deleted = await rl.rotate_old_records(session)
    assert deleted == 5

    rows = (await session.execute(select(RateLimit))).scalars().all()
    assert len(rows) == 3


async def test_rotate_no_op_when_clean(session):
    rl = RateLimiter()
    deleted = await rl.rotate_old_records(session)
    assert deleted == 0
