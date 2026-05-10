"""Orchestrates pre-filter → Claude → geo-reject → DB write. See spec §6.2."""
from datetime import datetime

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from leads_bot.analyzer.claude_client import ClaudeAnalyzerClient
from leads_bot.analyzer.geo_filter import has_ru_markers
from leads_bot.analyzer.prompts import ANALYZER_SYSTEM, build_analyzer_prompt
from leads_bot.config import get_settings
from leads_bot.db.models import Lead


class Analyzer:
    def __init__(self, claude: ClaudeAnalyzerClient | None = None):
        self._claude = claude or ClaudeAnalyzerClient()
        self._settings = get_settings()

    async def analyze_and_persist(
        self,
        session: AsyncSession,
        lead: Lead,
        channel_title: str,
        channel_language: str,
    ) -> Lead:
        """Analyze a Lead row in-place, set fields, set status. Returns same Lead."""
        # Hard reject by RU markers BEFORE calling Claude — saves cost
        if has_ru_markers(lead.raw_text):
            lead.is_lead = False
            lead.client_country = "ru"
            lead.reasoning = "Hard reject: RU markers in text"
            lead.status = "filtered_out"
            lead.analyzed_at = datetime.utcnow()
            await session.commit()
            return lead

        prompt = build_analyzer_prompt(lead.raw_text, channel_title, channel_language)
        try:
            data = await self._claude.analyze(ANALYZER_SYSTEM, prompt)
        except Exception as e:
            logger.exception(f"Analyzer failed for lead {lead.id}: {e}")
            lead.status = "analysis_failed"
            lead.analyzed_at = datetime.utcnow()
            await session.commit()
            return lead

        lead.is_lead = bool(data.get("is_lead"))
        lead.project_type = data.get("project_type")
        lead.budget_usd = data.get("budget_usd")
        lead.language = data.get("language")
        lead.client_country = data.get("client_country")
        lead.urgency = data.get("urgency")
        lead.relevance_score = int(data.get("relevance_score") or 0)
        lead.reasoning = data.get("reasoning")
        lead.analyzed_at = datetime.utcnow()

        if lead.client_country == "ru":
            lead.status = "filtered_out"
        elif not lead.is_lead:
            lead.status = "filtered_out"
        elif (lead.budget_usd or 0) < self._settings.min_budget_usd:
            lead.status = "filtered_out"
        elif lead.relevance_score < self._settings.min_relevance_score:
            lead.status = "filtered_out"
        else:
            lead.status = "drafted"  # passed filters; drafter will create response

        await session.commit()
        return lead
