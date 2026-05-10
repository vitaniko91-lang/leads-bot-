"""FastAPI dependencies for DB session, settings, etc.

The session_factory dep is overridable in tests via app.dependency_overrides.
"""
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from leads_bot.config import Settings, get_settings
from leads_bot.db.session import get_session_factory


def get_settings_dep() -> Settings:
    return get_settings()


def get_session_factory_dep() -> async_sessionmaker[AsyncSession]:
    return get_session_factory()


async def get_session(
    factory: Annotated[
        async_sessionmaker[AsyncSession], Depends(get_session_factory_dep)
    ],
) -> AsyncIterator[AsyncSession]:
    async with factory() as s:
        yield s
