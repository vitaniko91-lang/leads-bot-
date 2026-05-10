import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from leads_bot.db.models import (
    Base,
    DiscoveryCandidate,
    Lead,
    Response,
    Source,
    Template,
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


async def test_template_create_with_defaults(session):
    t = Template(
        name="Friendly + portfolio (A)",
        prompt="You are a friendly designer's assistant...",
        variant="A",
        active=True,
        traffic_share=40,
    )
    session.add(t)
    await session.commit()
    assert t.id is not None
    assert t.sent_count == 0
    assert t.reply_count == 0


async def test_response_template_fk_links(session):
    src = Source(tg_id=-1, title="x", type="channel", language="ru", region="ua")
    session.add(src)
    await session.commit()
    lead = Lead(source_id=src.id, tg_message_id=1, raw_text="x", status="drafted")
    session.add(lead)
    await session.commit()

    tpl = Template(name="A", prompt="...", variant="A", active=True, traffic_share=100)
    session.add(tpl)
    await session.commit()

    resp = Response(
        lead_id=lead.id, template_id=tpl.id, draft_text="hi",
        status="drafted", sent_to="dm", author_tg_id_cached=99999,
    )
    session.add(resp)
    await session.commit()
    assert resp.template_id == tpl.id
    assert resp.author_tg_id_cached == 99999


async def test_discovery_candidate_create(session):
    c = DiscoveryCandidate(
        tg_id=-100, title="Design Jobs Berlin",
        description="EU jobs", member_count=4500,
        language="en", predicted_region="eu", status="pending",
    )
    session.add(c)
    await session.commit()
    assert c.id is not None


async def test_response_has_author_index(session):
    indexes = {idx.name for idx in Response.__table__.indexes}
    assert "ix_responses_author_status_sent" in indexes
