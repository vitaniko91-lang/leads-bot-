"""Generates draft replies via Claude. See spec §6.3."""
from anthropic import AsyncAnthropic
from loguru import logger

from leads_bot.config import get_settings
from leads_bot.drafter.profile import Profile
from leads_bot.drafter.prompts import DRAFTER_SYSTEM, build_drafter_prompt


class Drafter:
    def __init__(self, profile: Profile, client: AsyncAnthropic | None = None):
        self._profile = profile
        self._settings = get_settings()
        self._client = client or AsyncAnthropic(api_key=self._settings.anthropic_api_key)

    async def draft(self, lead_text: str, project_type: str, client_language: str) -> str:
        prompt = build_drafter_prompt(
            profile=self._profile,
            lead_text=lead_text,
            project_type=project_type or "other",
            client_language=client_language or "en",
        )
        msg = await self._client.messages.create(
            model=self._settings.drafter_model,
            max_tokens=400,
            system=DRAFTER_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text.strip()
        logger.info(f"Drafted reply ({len(text)} chars) for {client_language} lead")
        return text
