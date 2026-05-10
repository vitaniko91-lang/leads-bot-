"""Async SQLAlchemy session factory."""
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from leads_bot.config import get_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(get_settings().database_url, echo=False)

        @event.listens_for(_engine.sync_engine, "connect")
        def _enable_wal(dbapi_conn, _):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA synchronous=NORMAL")
            cur.close()
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _session_factory


async def ensure_bot_state(factory: async_sessionmaker[AsyncSession]) -> None:
    """Insert the singleton BotState(id=1) row if missing. Idempotent."""
    from sqlalchemy import select

    from leads_bot.db.models import BotState

    async with factory() as session:
        existing = (await session.execute(
            select(BotState).where(BotState.id == 1)
        )).scalar_one_or_none()
        if existing is None:
            session.add(BotState(id=1, paused=False, consecutive_health_fails=0))
            await session.commit()
