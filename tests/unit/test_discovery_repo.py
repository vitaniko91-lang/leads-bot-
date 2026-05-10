import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from leads_bot.db.models import Base, Source
from leads_bot.discovery.repo import DiscoveryRepo
from leads_bot.discovery.searcher import RawCandidate


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


def _raw(tg_id, title="x", members=1000):
    return RawCandidate(
        tg_id=tg_id, title=title, description="", member_count=members,
        predicted_region="eu", predicted_language="en", matched_query="q",
    )


async def test_insert_new_candidates(session):
    repo = DiscoveryRepo(session)
    inserted = await repo.upsert_pending([_raw(1), _raw(2)])
    assert inserted == 2


async def test_skip_existing_by_tg_id(session):
    repo = DiscoveryRepo(session)
    await repo.upsert_pending([_raw(1)])
    inserted = await repo.upsert_pending([_raw(1), _raw(2)])
    assert inserted == 1


async def test_skip_when_already_in_sources(session):
    src = Source(
        tg_id=999, title="s", type="channel",
        language="en", region="eu", status="active",
    )
    session.add(src); await session.commit()

    repo = DiscoveryRepo(session)
    inserted = await repo.upsert_pending([_raw(999)])
    assert inserted == 0


async def test_pending_top_n_sorted_by_members(session):
    repo = DiscoveryRepo(session)
    await repo.upsert_pending([
        _raw(1, "A", members=100),
        _raw(2, "B", members=5000),
        _raw(3, "C", members=2500),
    ])
    top = await repo.pending(limit=2)
    assert [c.title for c in top] == ["B", "C"]


async def test_approve_creates_source_and_marks_approved(session):
    repo = DiscoveryRepo(session)
    await repo.upsert_pending([_raw(7, "Cool channel")])
    [cand] = await repo.pending()
    src = await repo.approve(cand.id)
    assert src.tg_id == 7
    assert src.title == "Cool channel"
    assert src.status == "active"

    refreshed = await repo.get(cand.id)
    assert refreshed.status == "approved"


async def test_reject_marks_rejected(session):
    repo = DiscoveryRepo(session)
    await repo.upsert_pending([_raw(8)])
    [cand] = await repo.pending()
    await repo.reject(cand.id)
    refreshed = await repo.get(cand.id)
    assert refreshed.status == "rejected"
    inserted = await repo.upsert_pending([_raw(8)])
    assert inserted == 0
