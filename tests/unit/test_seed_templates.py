import json

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from leads_bot.db.models import Base, Template
from leads_bot.db.seed_templates import seed_templates_from_json


@pytest.fixture
async def factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
def seed_file(tmp_path):
    p = tmp_path / "templates.json"
    p.write_text(json.dumps([
        {"name": "A", "variant": "A", "active": True, "traffic_share": 50, "prompt": "p1"},
        {"name": "B", "variant": "B", "active": True, "traffic_share": 50, "prompt": "p2"},
    ]))
    return p


async def test_seed_inserts_when_empty(factory, seed_file):
    added = await seed_templates_from_json(seed_file, factory)
    assert added == 2
    async with factory() as s:
        rows = (await s.execute(select(Template))).scalars().all()
        assert len(rows) == 2


async def test_seed_is_idempotent(factory, seed_file):
    await seed_templates_from_json(seed_file, factory)
    added = await seed_templates_from_json(seed_file, factory)
    assert added == 0
    async with factory() as s:
        rows = (await s.execute(select(Template))).scalars().all()
        assert len(rows) == 2


async def test_seed_rejects_bad_traffic_sum(factory, tmp_path):
    p = tmp_path / "bad.json"
    p.write_text(json.dumps([
        {"name": "A", "variant": "A", "active": True, "traffic_share": 60, "prompt": "p"},
        {"name": "B", "variant": "B", "active": True, "traffic_share": 60, "prompt": "p"},
    ]))
    with pytest.raises(ValueError, match="traffic_share"):
        await seed_templates_from_json(p, factory)
