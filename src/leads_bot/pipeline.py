"""Wires listener → analyzer → drafter → notifier. See spec §7."""
from datetime import datetime
from zoneinfo import ZoneInfo

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from leads_bot.analyzer.analyzer import Analyzer
from leads_bot.config import get_settings
from leads_bot.db.models import BotState, Lead, Response, Source
from leads_bot.drafter.drafter import Drafter
from leads_bot.notifier.bot import send_lead_card
from leads_bot.notifier.card import build_keyboard, format_lead_card
from leads_bot.time_utils import is_in_quiet_window, parse_window


def _utcnow_aware() -> datetime:
    """Wrappable for tests."""
    return datetime.now(ZoneInfo("UTC"))


class Pipeline:
    def __init__(
        self, analyzer: Analyzer, drafter: Drafter, bot,
        owner_tg_id: int,
        factory: async_sessionmaker | None = None,
        templates=None,  # TemplateRepo, kept for parity (drafter already holds one)
    ):
        self._analyzer = analyzer
        self._drafter = drafter
        self._bot = bot
        self._owner = owner_tg_id
        self._factory = factory
        self._templates = templates
        self._settings = get_settings()

    async def _is_paused(self, session: AsyncSession) -> bool:
        bs = (await session.execute(
            select(BotState).where(BotState.id == 1)
        )).scalar_one_or_none()
        return bool(bs and bs.paused)

    async def _quiet_window(
        self, session: AsyncSession,
    ) -> tuple[tuple[int, int], tuple[int, int]] | None:
        if not self._settings.quiet_hours_enabled:
            return None
        bs = (await session.execute(
            select(BotState).where(BotState.id == 1)
        )).scalar_one_or_none()
        spec = (bs.quiet_hours_override if bs and bs.quiet_hours_override
                else self._settings.quiet_hours)
        return parse_window(spec)

    async def process_new_lead(
        self, session: AsyncSession, lead: Lead, source: Source,
    ) -> None:
        if await self._is_paused(session):
            logger.info(f"Bot paused — ignoring lead {lead.id}")
            return

        analyzed = await self._analyzer.analyze_and_persist(
            session, lead, source.title, source.language,
        )
        if analyzed.status == "filtered_out":
            logger.info(f"Lead {lead.id} filtered out: {analyzed.reasoning}")
            return
        if analyzed.status == "analysis_failed":
            logger.warning(f"Lead {lead.id} analysis failed — manual retry needed")
            return

        sent_to = "dm" if self._wants_dm(analyzed.raw_text) else "chat"

        try:
            draft = await self._drafter.draft(
                lead_text=analyzed.raw_text,
                project_type=analyzed.project_type or "other",
                client_language=analyzed.language or "en",
            )
        except Exception as e:
            logger.exception(f"Drafter failed for lead {lead.id}: {e}")
            analyzed.status = "analysis_failed"
            await session.commit()
            return

        quiet = await self._quiet_window(session)
        in_quiet = quiet and is_in_quiet_window(_utcnow_aware(), *quiet)

        response = Response(
            lead_id=lead.id,
            template_id=draft.template_id,
            author_tg_id_cached=lead.author_tg_id,
            draft_text=draft.text,
            status="pending_digest" if in_quiet else "drafted",
            sent_to=sent_to,
        )
        session.add(response)
        await session.commit()

        if in_quiet:
            logger.info(f"Lead {lead.id} queued for morning digest (quiet hours)")
            return

        await session.refresh(lead, attribute_names=["source"])
        card = format_lead_card(lead, response)
        kb = build_keyboard(response_id=response.id, source_id=source.id)
        await send_lead_card(self._bot, self._owner, card, kb)

    async def regenerate_draft(self, lead_id: int) -> None:
        """Regenerate the draft for an existing lead and resend the card to owner."""
        from leads_bot.db.session import get_session_factory
        factory = self._factory or get_session_factory()
        async with factory() as session:
            lead = (await session.execute(
                select(Lead).where(Lead.id == lead_id)
            )).scalar_one_or_none()
            if lead is None:
                raise ValueError(f"Lead {lead_id} not found")
            await session.refresh(lead, attribute_names=["source"])
            try:
                draft = await self._drafter.draft(
                    lead_text=lead.raw_text,
                    project_type=lead.project_type or "other",
                    client_language=lead.language or "en",
                )
            except Exception as e:
                logger.exception(f"Drafter retry failed for lead {lead_id}: {e}")
                raise
            response = Response(
                lead_id=lead.id,
                template_id=draft.template_id,
                author_tg_id_cached=lead.author_tg_id,
                draft_text=draft.text,
                status="drafted",
                sent_to="dm" if self._wants_dm(lead.raw_text) else "chat",
            )
            session.add(response)
            await session.commit()
            card = format_lead_card(lead, response)
            kb = build_keyboard(response_id=response.id, source_id=lead.source.id)
            await send_lead_card(self._bot, self._owner, card, kb)

    @staticmethod
    def _wants_dm(text: str) -> bool:
        lower = text.lower()
        return any(s in lower for s in [
            "в лс", "пишите в", "write in dm", "dm me", "dms open", "in dm",
        ])
