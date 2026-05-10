import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from leads_bot.db.models import Base, Template
from leads_bot.templates.repo import TemplateRepo


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def _seed(session, *items):
    for kw in items:
        kw.setdefault("variant", "A")
        kw.setdefault("active", True)
        kw.setdefault("traffic_share", 100)
        kw.setdefault("prompt", "p")
        session.add(Template(**kw))
    await session.commit()


async def test_active_returns_only_active(session):
    await _seed(session,
        {"name": "on", "active": True, "traffic_share": 100},
        {"name": "off", "active": False, "traffic_share": 0},
    )
    repo = TemplateRepo(session)
    rows = await repo.active()
    assert {t.name for t in rows} == {"on"}


async def test_record_send_increments_sent(session):
    await _seed(session, {"name": "x"})
    repo = TemplateRepo(session)
    [t] = await repo.active()
    await repo.record_send(t.id)
    refreshed = await repo.get(t.id)
    assert refreshed.sent_count == 1


async def test_record_reply_increments_reply(session):
    await _seed(session, {"name": "x"})
    repo = TemplateRepo(session)
    [t] = await repo.active()
    await repo.record_reply(t.id)
    refreshed = await repo.get(t.id)
    assert refreshed.reply_count == 1


async def test_record_reply_handles_missing_id(session):
    repo = TemplateRepo(session)
    await repo.record_reply(9999)


async def test_update_prompt_and_share(session):
    await _seed(session, {"name": "x", "traffic_share": 50})
    repo = TemplateRepo(session)
    [t] = await repo.active()
    await repo.update(t.id, prompt="new prompt", traffic_share=75)
    refreshed = await repo.get(t.id)
    assert refreshed.prompt == "new prompt"
    assert refreshed.traffic_share == 75


async def test_validate_traffic_sum_raises_on_mismatch(session):
    await _seed(session,
        {"name": "a", "traffic_share": 60},
        {"name": "b", "traffic_share": 30},
    )
    repo = TemplateRepo(session)
    with pytest.raises(ValueError, match="must sum to 100"):
        await repo.validate_traffic_sum()
