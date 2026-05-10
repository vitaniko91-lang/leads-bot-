from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from leads_bot.db.models import Base
from leads_bot.discovery.scheduler import DiscoveryScheduler
from leads_bot.discovery.searcher import RawCandidate


@pytest.fixture
async def factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def test_scan_invokes_searcher_and_persists(factory):
    raws = [RawCandidate(1, "A", "", 1000, "eu", "en", "q")]
    searcher = MagicMock()
    searcher.run_all = AsyncMock(return_value=raws)

    sched = DiscoveryScheduler(
        searcher=searcher, factory=factory, bot=MagicMock(),
        owner_tg_id=999, timezone="Asia/Bangkok",
    )
    inserted = await sched.scan_now()
    assert inserted == 1


async def test_send_digest_messages_owner(factory):
    bot = MagicMock(); bot.send_message = AsyncMock()
    sched = DiscoveryScheduler(
        searcher=MagicMock(), factory=factory, bot=bot,
        owner_tg_id=999, timezone="Asia/Bangkok",
    )
    await sched.send_digest_now()
    assert bot.send_message.await_count >= 1
    args = bot.send_message.await_args_list[0]
    assert args.args[0] == 999


def test_scheduler_registers_two_jobs(factory):
    sched = DiscoveryScheduler(
        searcher=MagicMock(), factory=factory, bot=MagicMock(),
        owner_tg_id=999, timezone="Asia/Bangkok",
    )
    sched.start()
    job_ids = {j.id for j in sched._scheduler.get_jobs()}
    assert "discovery_scan_weekly" in job_ids
    assert "discovery_digest_weekly" in job_ids
    sched.stop()
