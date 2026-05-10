"""Sends approved replies via Telethon. See spec §6.5."""
import asyncio
from datetime import datetime

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from telethon.errors import (
    ChatWriteForbiddenError,
    FloodWaitError,
    PeerIdInvalidError,
    UserIsBlockedError,
)

from leads_bot.db.models import Lead, Response
from leads_bot.sender.rate_limiter import RateLimiter


class Sender:
    def __init__(self, telethon_client, rate_limiter: RateLimiter | None = None):
        self._client = telethon_client
        self._rl = rate_limiter or RateLimiter()

    async def send(self, session: AsyncSession, response_id: int) -> None:
        """Apply rate-limit, sleep antiban delay, send via Telethon, update DB."""
        resp = (await session.execute(
            select(Response).where(Response.id == response_id)
        )).scalar_one()
        lead = (await session.execute(
            select(Lead).where(Lead.id == resp.lead_id)
        )).scalar_one()

        await self._rl.check_and_record(session)

        delay = self._rl.random_delay_seconds()
        logger.info(f"Sender: sleeping {delay}s before sending response {response_id}")
        await asyncio.sleep(delay)

        target = self._resolve_target(lead, resp)
        text = resp.final_text or resp.draft_text

        try:
            try:
                async with self._client.action(target, "typing"):
                    await asyncio.sleep(min(5, max(2, len(text) // 100)))
            except Exception:  # typing indicator is best-effort
                pass
            await self._client.send_message(target, text)
        except (UserIsBlockedError, ChatWriteForbiddenError, PeerIdInvalidError) as e:
            logger.warning(f"Send failed (terminal): {type(e).__name__}")
            resp.status = "failed"
            resp.notes = f"failed: {type(e).__name__}"
            await session.commit()
            return
        except FloodWaitError as e:
            logger.error(f"FloodWait {e.seconds}s — will retry next cycle")
            resp.status = "drafted"
            await session.commit()
            raise

        resp.status = "sent"
        resp.sent_at = datetime.utcnow()
        await session.commit()
        logger.info(f"Sent response {response_id}")

        if resp.template_id is not None:
            from leads_bot.templates.repo import TemplateRepo
            await TemplateRepo(session).record_send(resp.template_id)

    def _resolve_target(self, lead: Lead, resp: Response):
        """Decide target based on resp.sent_to."""
        if resp.sent_to == "dm":
            if lead.author_username:
                return f"@{lead.author_username}"
            if lead.author_tg_id:
                return lead.author_tg_id
        return lead.source.tg_id if lead.source else lead.author_tg_id
