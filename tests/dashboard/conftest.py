"""Shared fixtures for dashboard API tests.

Each test gets:
- An in-memory SQLite engine + sessionmaker.
- A FastAPI app whose `get_session_factory_dep` is overridden to that engine.
- An httpx.AsyncClient bound to the app via ASGITransport.
- HTTP Basic credentials pre-encoded.
"""
import base64
from collections.abc import AsyncIterator
from datetime import datetime

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from leads_bot.dashboard.app import create_app
from leads_bot.dashboard.deps import get_session_factory_dep
from leads_bot.db.models import Base


@pytest.fixture(autouse=True)
def _env(monkeypatch, tmp_path):
    """Provide a complete env so leads_bot.config.Settings() validates."""
    for k, v in [
        ("TELEGRAM_API_ID", "1"),
        ("TELEGRAM_API_HASH", "x"),
        ("TELEGRAM_PHONE", "+1"),
        ("BOT_TOKEN", "x"),
        ("OWNER_TG_ID", "1"),
        ("ANTHROPIC_API_KEY", "x"),
        ("DASHBOARD_USER", "vita"),
        ("DASHBOARD_PASSWORD", "secret"),
        ("DATA_DIR", str(tmp_path)),
    ]:
        monkeypatch.setenv(k, v)
    from leads_bot import config
    config._settings = None
    yield
    config._settings = None


@pytest.fixture
def basic_auth_header() -> dict[str, str]:
    raw = base64.b64encode(b"vita:secret").decode()
    return {"Authorization": f"Basic {raw}"}


@pytest.fixture
def wrong_auth_header() -> dict[str, str]:
    raw = base64.b64encode(b"vita:wrong").decode()
    return {"Authorization": f"Basic {raw}"}


@pytest.fixture
async def engine():
    e = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with e.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield e
    await e.dispose()


@pytest.fixture
async def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
async def client(session_factory) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app()
    from leads_bot.dashboard.routes import register_all
    register_all(app)

    app.dependency_overrides[get_session_factory_dep] = lambda: session_factory
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def seeded(session_factory):
    """Seed minimal data: one source, three leads, two responses."""
    from leads_bot.db.models import Lead, Response, Source

    async with session_factory() as s:
        src = Source(
            tg_id=-1001, title="Design Jobs UA", type="channel",
            language="ru", region="ua", status="active",
            added_at=datetime(2026, 5, 1),
        )
        s.add(src)
        await s.commit()
        leads = [
            Lead(source_id=src.id, tg_message_id=1, raw_text="Looking for UI",
                 is_lead=True, project_type="landing", budget_usd=1500,
                 language="en", client_country="eu", urgency="med",
                 relevance_score=88, reasoning="ok",
                 status="sent", posted_at=datetime(2026, 5, 22, 10),
                 analyzed_at=datetime(2026, 5, 22, 10, 1)),
            Lead(source_id=src.id, tg_message_id=2, raw_text="Шукаю дизайнера",
                 is_lead=True, project_type="app", budget_usd=600,
                 language="uk", client_country="ua", urgency="low",
                 relevance_score=72, reasoning="ok",
                 status="drafted", posted_at=datetime(2026, 5, 22, 11)),
            Lead(source_id=src.id, tg_message_id=3, raw_text="Сбер",
                 is_lead=False, client_country="ru",
                 status="filtered_out", posted_at=datetime(2026, 5, 22, 12)),
        ]
        s.add_all(leads)
        await s.commit()
        responses = [
            Response(lead_id=leads[0].id, draft_text="Hi! Saw your post...",
                     final_text="Hi! Saw your post...",
                     status="sent", sent_to="dm",
                     sent_at=datetime(2026, 5, 22, 10, 2),
                     client_replied=True, client_status="in_dialog"),
            Response(lead_id=leads[1].id, draft_text="Привіт! Бачила...",
                     status="drafted", sent_to="chat"),
        ]
        s.add_all(responses)
        await s.commit()
    return {"source_id": src.id, "lead_ids": [l.id for l in leads]}
