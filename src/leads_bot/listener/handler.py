"""Wires Telethon NewMessage → pre-filter → pipeline. See spec §6.1."""
from datetime import datetime

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from telethon import events

from leads_bot.db.models import Lead, Source
from leads_bot.listener.filters import looks_like_lead


def register_listener(client, session_factory: async_sessionmaker, on_new_lead):
    """Subscribe to NewMessage in all active sources.

    `on_new_lead` is async callback(session, lead, source).
    """

    @client.on(events.NewMessage())
    async def _handler(event):
        chat_id = event.chat_id
        text = event.raw_text or ""

        if not looks_like_lead(text):
            return

        async with session_factory() as session:
            src = (await session.execute(
                select(Source).where(
                    Source.tg_id == chat_id, Source.status == "active"
                )
            )).scalar_one_or_none()
            if not src:
                return  # not a tracked source

            if src.muted_until and src.muted_until > datetime.utcnow():
                return

            existing = (await session.execute(
                select(Lead).where(
                    Lead.source_id == src.id,
                    Lead.tg_message_id == event.id,
                )
            )).scalar_one_or_none()
            if existing:
                return

            posted_at = event.date.replace(tzinfo=None) if event.date else datetime.utcnow()
            lead = Lead(
                source_id=src.id,
                tg_message_id=event.id,
                author_tg_id=event.sender_id,
                author_username=getattr(event.sender, "username", None),
                raw_text=text,
                posted_at=posted_at,
                status="new",
            )
            session.add(lead)
            src.last_msg_at = datetime.utcnow()
            await session.commit()

            try:
                await on_new_lead(session, lead, src)
            except Exception as e:
                logger.exception(f"on_new_lead failed for lead {lead.id}: {e}")
