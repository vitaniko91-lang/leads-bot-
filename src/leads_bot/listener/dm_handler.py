"""Detects when a previously-contacted lead writes back via DM.

Pure function `process_incoming_dm` is the testable core.
`register_dm_listener` wires it to a Telethon NewMessage(incoming, is_private)
handler.
"""
from datetime import datetime, timedelta

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from telethon import events

from leads_bot.db.models import Lead, Response
from leads_bot.templates.repo import TemplateRepo

REPLY_WINDOW_DAYS = 7


async def process_incoming_dm(
    factory: async_sessionmaker,
    sender_id: int,
    dm_date_utc: datetime,
    notifier,
) -> None:
    """Called for every incoming DM. Handles client-reply detection.

    - Finds Responses we sent to `sender_id` in the last 7 days that:
      * status='sent' AND sent_at IS NOT NULL
      * sent_at < dm_date_utc        (prevents pre-reply race condition)
      * client_replied = False       (idempotent)
    - For the most recent matching response, sets client_replied,
      increments the template's reply_count, and fires owner notification.
    """
    cutoff = datetime.utcnow() - timedelta(days=REPLY_WINDOW_DAYS)
    if dm_date_utc.tzinfo is not None:
        dm_naive = dm_date_utc.replace(tzinfo=None)
    else:
        dm_naive = dm_date_utc

    async with factory() as session:
        stmt = (
            select(Response)
            .where(
                Response.author_tg_id_cached == sender_id,
                Response.status == "sent",
                Response.sent_at.is_not(None),
                Response.sent_at >= cutoff,
                Response.sent_at < dm_naive,
                Response.client_replied.is_(False),
            )
            .order_by(Response.sent_at.desc())
            .limit(1)
        )
        resp = (await session.execute(stmt)).scalar_one_or_none()
        if resp is None:
            return

        resp.client_replied = True
        resp.client_replied_at = dm_naive
        if resp.client_status is None:
            resp.client_status = "replied"
        await session.commit()

        await TemplateRepo(session).record_reply(resp.template_id)

        lead = await session.get(Lead, resp.lead_id)
        try:
            await notifier.notify(lead, resp)
        except Exception as e:
            logger.exception(f"DM-reply notify failed for response {resp.id}: {e}")


def register_dm_listener(client, factory: async_sessionmaker, notifier):
    """Subscribe Telethon to incoming private messages from any user."""

    @client.on(events.NewMessage(incoming=True))
    async def _on_dm(event):
        if not event.is_private:
            return
        sender_id = event.sender_id
        if sender_id is None:
            return
        dm_date = event.date or datetime.utcnow()
        try:
            await process_incoming_dm(
                factory, sender_id=sender_id, dm_date_utc=dm_date, notifier=notifier,
            )
        except Exception as e:
            logger.exception(f"DM handler error: {e}")
