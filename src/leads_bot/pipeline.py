"""Wires listener → analyzer → drafter → notifier. See spec §7."""
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from leads_bot.analyzer.analyzer import Analyzer
from leads_bot.db.models import Lead, Response, Source
from leads_bot.drafter.drafter import Drafter
from leads_bot.notifier.bot import send_lead_card
from leads_bot.notifier.card import build_keyboard, format_lead_card


class Pipeline:
    def __init__(self, analyzer: Analyzer, drafter: Drafter, bot, owner_tg_id: int):
        self._analyzer = analyzer
        self._drafter = drafter
        self._bot = bot
        self._owner = owner_tg_id

    async def process_new_lead(
        self, session: AsyncSession, lead: Lead, source: Source
    ) -> None:
        """Full path: analyze → if pass, draft → notify owner."""
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
            draft_text = await self._drafter.draft(
                lead_text=analyzed.raw_text,
                project_type=analyzed.project_type or "other",
                client_language=analyzed.language or "en",
            )
        except Exception as e:
            logger.exception(f"Drafter failed for lead {lead.id}: {e}")
            analyzed.status = "analysis_failed"
            await session.commit()
            return

        response = Response(
            lead_id=lead.id,
            draft_text=draft_text,
            status="drafted",
            sent_to=sent_to,
        )
        session.add(response)
        await session.commit()

        await session.refresh(lead, attribute_names=["source"])

        card = format_lead_card(lead, response)
        kb = build_keyboard(response_id=response.id, source_id=source.id)
        await send_lead_card(self._bot, self._owner, card, kb)

    @staticmethod
    def _wants_dm(text: str) -> bool:
        lower = text.lower()
        return any(s in lower for s in [
            "в лс", "пишите в", "write in dm", "dm me", "dms open", "in dm",
        ])
