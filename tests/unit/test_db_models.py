import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from leads_bot.db.models import Base, Lead, Source


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    s = AsyncSession(engine, expire_on_commit=False)
    yield s
    await s.close()
    await engine.dispose()


async def test_create_source(session):
    src = Source(
        tg_id=-1001234567890,
        title="Design Jobs UA",
        type="channel",
        language="ru",
        region="ua",
        status="active",
    )
    session.add(src)
    await session.commit()
    assert src.id is not None


async def test_lead_dedup_by_source_and_message(session):
    src = Source(
        tg_id=-100, title="x", type="channel", language="en", region="eu", status="active"
    )
    session.add(src)
    await session.commit()

    l1 = Lead(source_id=src.id, tg_message_id=42, raw_text="hi", status="new")
    l2 = Lead(source_id=src.id, tg_message_id=42, raw_text="hi again", status="new")
    session.add_all([l1, l2])
    with pytest.raises(IntegrityError):
        await session.commit()


async def test_region_field_accepts_valid_values(session):
    src = Source(
        tg_id=1, title="x", type="channel", language="en", region="eu", status="active"
    )
    session.add(src)
    await session.commit()
    assert src.region == "eu"


async def test_botstate_singleton_row(session):
    from leads_bot.db.models import BotState

    s = BotState(id=1, paused=False, consecutive_health_fails=0)
    session.add(s)
    await session.commit()
    assert s.id == 1
    assert s.paused is False
    assert s.consecutive_health_fails == 0
