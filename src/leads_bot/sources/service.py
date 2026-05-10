"""CRUD service for `sources` table.

Telethon is used only to RESOLVE a link/username into a tg_id + title; all DB
work is plain SQLAlchemy and is fully testable with a mocked client.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from telethon.utils import get_peer_id

from leads_bot.db.models import Source

ALLOWED_REGIONS = {"ua", "cis_ex_ru", "eu", "en_global"}
_LINK_RE = re.compile(r"^(?:https?://)?(?:t\.me/|telegram\.me/)?@?(?P<u>[A-Za-z0-9_]{4,})/?$")


class SourceAlreadyExists(Exception):
    pass


class SourceNotFound(Exception):
    pass


class InvalidRegion(Exception):
    pass


class InvalidLink(Exception):
    pass


@dataclass(frozen=True)
class SourceView:
    """Read-only DTO returned by `list_sources` (avoids leaking ORM rows)."""
    id: int
    tg_id: int
    title: str
    type: str
    language: str
    region: str
    status: str


def _parse_link(link: str) -> str:
    """Extract bare username from a t.me URL, @handle, or plain username."""
    link = link.strip()
    m = _LINK_RE.match(link)
    if not m:
        raise InvalidLink(f"Cannot parse link: {link!r}")
    return m.group("u")


async def list_sources(factory: async_sessionmaker) -> list[SourceView]:
    async with factory() as session:
        rows = (await session.execute(
            select(Source).order_by(Source.id)
        )).scalars().all()
        return [
            SourceView(
                id=r.id, tg_id=r.tg_id, title=r.title, type=r.type,
                language=r.language, region=r.region, status=r.status,
            )
            for r in rows
        ]


async def add_source_from_link(
    factory: async_sessionmaker,
    client,
    link: str,
    region: str,
    language: str,
) -> SourceView:
    """Resolve `link` via Telethon, then INSERT into sources.

    Raises InvalidRegion / InvalidLink / SourceAlreadyExists.
    """
    if region not in ALLOWED_REGIONS:
        raise InvalidRegion(
            f"region must be one of {sorted(ALLOWED_REGIONS)}, got {region!r}"
        )

    username = _parse_link(link)
    entity = await client.get_entity(username)
    tg_id = get_peer_id(entity)
    title = getattr(entity, "title", None) or username
    type_ = "group" if getattr(entity, "megagroup", False) else "channel"

    async with factory() as session:
        existing = (await session.execute(
            select(Source).where(Source.tg_id == tg_id)
        )).scalar_one_or_none()
        if existing:
            raise SourceAlreadyExists(
                f"Source with tg_id={tg_id} already exists (id={existing.id})"
            )
        row = Source(
            tg_id=tg_id, title=title, type=type_,
            language=language, region=region, status="active",
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        logger.info(f"Added source {row.id}: {title} ({tg_id})")
        return SourceView(
            id=row.id, tg_id=row.tg_id, title=row.title, type=row.type,
            language=row.language, region=row.region, status=row.status,
        )


async def pause_source(factory: async_sessionmaker, source_id: int) -> None:
    async with factory() as session:
        row = (await session.execute(
            select(Source).where(Source.id == source_id)
        )).scalar_one_or_none()
        if not row:
            raise SourceNotFound(f"No source with id={source_id}")
        row.status = "paused"
        await session.commit()


async def resume_source(factory: async_sessionmaker, source_id: int) -> None:
    async with factory() as session:
        row = (await session.execute(
            select(Source).where(Source.id == source_id)
        )).scalar_one_or_none()
        if not row:
            raise SourceNotFound(f"No source with id={source_id}")
        row.status = "active"
        await session.commit()
