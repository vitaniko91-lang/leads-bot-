"""Generates draft replies via Claude. See spec §6.3.

Iter 4: picks one of the active Templates weighted by traffic_share, uses its
`prompt` as the system message, and returns the chosen template_id alongside
the draft text. Falls back to the hardcoded DRAFTER_SYSTEM only when no
active templates exist (boot-time / migration safety).
"""
from dataclasses import dataclass

from anthropic import AsyncAnthropic
from loguru import logger

from leads_bot.config import get_settings
from leads_bot.drafter.profile import Profile
from leads_bot.drafter.prompts import DRAFTER_SYSTEM, build_drafter_prompt
from leads_bot.templates.picker import NoActiveTemplatesError, pick_template
from leads_bot.templates.repo import TemplateRepo


@dataclass(frozen=True)
class DraftResult:
    text: str
    template_id: int | None  # None => fallback DRAFTER_SYSTEM was used


class Drafter:
    def __init__(
        self,
        profile: Profile,
        templates: TemplateRepo,
        client: AsyncAnthropic | None = None,
    ):
        self._profile = profile
        self._templates = templates
        self._settings = get_settings()
        self._client = client or AsyncAnthropic(api_key=self._settings.anthropic_api_key)

    async def draft(
        self,
        lead_text: str,
        project_type: str,
        client_language: str,
    ) -> DraftResult:
        active = await self._templates.active()
        try:
            tpl = pick_template(active)
            system = tpl.prompt
            template_id = tpl.id
            logger.info(f"Drafter: using template '{tpl.name}' (variant {tpl.variant})")
        except NoActiveTemplatesError:
            system = DRAFTER_SYSTEM
            template_id = None
            logger.warning("Drafter: no active templates — using fallback DRAFTER_SYSTEM")

        user = build_drafter_prompt(
            profile=self._profile,
            lead_text=lead_text,
            project_type=project_type or "other",
            client_language=client_language or "en",
        )
        msg = await self._client.messages.create(
            model=self._settings.drafter_model,
            max_tokens=400,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = msg.content[0].text.strip()
        logger.info(f"Drafted reply ({len(text)} chars) for {client_language} lead")
        return DraftResult(text=text, template_id=template_id)
