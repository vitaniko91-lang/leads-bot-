"""Thin async wrapper around Anthropic SDK for analyzer."""
import json
from typing import Any

from anthropic import AsyncAnthropic
from loguru import logger

from leads_bot.config import get_settings


class ClaudeAnalyzerClient:
    def __init__(self, client: AsyncAnthropic | None = None):
        self._settings = get_settings()
        self._client = client or AsyncAnthropic(api_key=self._settings.anthropic_api_key)

    async def analyze(self, system: str, user: str) -> dict[str, Any]:
        """Calls Claude, expects JSON response, returns parsed dict.

        Raises ValueError on invalid JSON.
        """
        msg = await self._client.messages.create(
            model=self._settings.analyzer_model,
            max_tokens=512,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = msg.content[0].text.strip()
        # Strip markdown code fences if Claude added them despite instructions
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.error(f"Claude returned invalid JSON: {text[:200]}")
            raise ValueError(f"Invalid JSON from Claude: {e}") from e
