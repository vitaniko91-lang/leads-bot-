from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from leads_bot.analytics.hot_hours import (
    HotHoursGrid,
    build_insight,
    compute_hot_hours,
)
from leads_bot.db.models import Base, Lead, Source


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def _add(session, src, posted_at):
    session.add(Lead(
        source_id=src.id, tg_message_id=int(posted_at.timestamp()),
        raw_text="x", posted_at=posted_at, status="new",
    ))


async def test_grid_shape_is_7_rows_24_cols(session):
    src = Source(tg_id=-1, title="x", type="channel", language="ru", region="ua")
    session.add(src); await session.commit()

    grid = await compute_hot_hours(session, days=30, owner_tz="Asia/Bangkok")
    assert isinstance(grid, HotHoursGrid)
    assert len(grid.matrix) == 7
    assert all(len(row) == 24 for row in grid.matrix)


async def test_utc_to_bangkok_conversion(session):
    """A lead at UTC 06:00 Monday should land at Bangkok 13:00 Monday (UTC+7)."""
    src = Source(tg_id=-1, title="x", type="channel", language="ru", region="ua")
    session.add(src); await session.commit()

    monday_06_utc = datetime(2026, 5, 4, 6, 0)
    await _add(session, src, monday_06_utc)
    await session.commit()

    grid = await compute_hot_hours(session, days=30, owner_tz="Asia/Bangkok")
    assert grid.matrix[0][13] == 1
    assert sum(sum(row) for row in grid.matrix) == 1


async def test_only_recent_n_days_counted(session):
    src = Source(tg_id=-1, title="x", type="channel", language="ru", region="ua")
    session.add(src); await session.commit()

    now = datetime.utcnow()
    await _add(session, src, now - timedelta(days=5))
    await _add(session, src, now - timedelta(days=40))
    await session.commit()

    grid = await compute_hot_hours(session, days=30, owner_tz="Asia/Bangkok")
    assert sum(sum(row) for row in grid.matrix) == 1


def test_insight_finds_top_window():
    grid = HotHoursGrid(
        matrix=[[0] * 24 for _ in range(7)], owner_tz="Asia/Bangkok",
    )
    grid.matrix[2][14] = 12
    grid.matrix[2][15] = 10
    grid.matrix[2][16] = 9
    grid.matrix[1][14] = 5

    text = build_insight(grid)
    assert "Wed" in text
    assert "14" in text
    assert "Asia/Bangkok" in text


def test_insight_handles_empty():
    grid = HotHoursGrid(matrix=[[0] * 24 for _ in range(7)], owner_tz="Asia/Bangkok")
    assert "no data" in build_insight(grid).lower() or "пока нет" in build_insight(grid).lower()
