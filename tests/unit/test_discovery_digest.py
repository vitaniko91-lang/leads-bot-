import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from leads_bot.db.models import Base, DiscoveryCandidate
from leads_bot.discovery.digest import (
    DigestRenderer,
    build_discovery_keyboard,
    format_candidate_line,
)


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


def _cand(**kw):
    base = dict(
        id=1, tg_id=-100, title="X", description="", member_count=1000,
        language="en", predicted_region="eu", status="pending",
    )
    base.update(kw)
    return DiscoveryCandidate(**base)


def test_format_line_includes_title_members_region():
    line = format_candidate_line(_cand(title="Design EU", member_count=4321, predicted_region="eu"))
    assert "Design EU" in line
    assert "4321" in line or "4.3K" in line or "4.3k" in line
    assert "eu" in line.lower() or "🇪🇺" in line


def test_keyboard_per_candidate_has_add_and_reject():
    kb = build_discovery_keyboard(candidate_id=42)
    flat = [b for row in kb.inline_keyboard for b in row]
    assert any("discover_add:42" in b.callback_data for b in flat)
    assert any("discover_reject:42" in b.callback_data for b in flat)


async def test_renderer_returns_one_message_per_candidate(session):
    session.add_all([
        _cand(id=1, tg_id=-1, title="A", member_count=5000),
        _cand(id=2, tg_id=-2, title="B", member_count=3000),
    ])
    await session.commit()

    r = DigestRenderer(session)
    msgs = await r.render(limit=10)
    # 1 header + 2 items
    assert len(msgs) == 3
    assert all("text" in m and "keyboard" in m for m in msgs)


async def test_renderer_empty_returns_one_no_results_message(session):
    r = DigestRenderer(session)
    msgs = await r.render(limit=10)
    assert len(msgs) == 1
    assert "нет новых" in msgs[0]["text"].lower() or "no new" in msgs[0]["text"].lower()
    assert msgs[0]["keyboard"] is None
