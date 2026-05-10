import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from leads_bot.drafter.drafter import Drafter
from leads_bot.drafter.profile import load_profile


@pytest.fixture
def profile(tmp_path, monkeypatch):
    for k, v in [
        ("TELEGRAM_API_ID", "1"), ("TELEGRAM_API_HASH", "x"),
        ("TELEGRAM_PHONE", "+1"), ("BOT_TOKEN", "x"),
        ("OWNER_TG_ID", "1"), ("ANTHROPIC_API_KEY", "x"),
    ]:
        monkeypatch.setenv(k, v)
    p = tmp_path / "profile.json"
    p.write_text(json.dumps({
        "name": "Vitalina", "portfolio_url": "https://x.design",
        "telegram": "@v", "min_rate_usd_per_hour": 50,
        "tone": "friendly", "payment_methods": ["wise"],
        "cases": [{"title": "Crypto", "tags": ["landing"],
                   "description": "x", "url": "u"}],
    }))
    return load_profile(p)


async def test_drafter_calls_claude_with_system_and_user(profile):
    fake_client = MagicMock()
    fake_msg = MagicMock()
    fake_msg.content = [MagicMock(text="Hi! Saw your post about a landing...")]
    fake_client.messages.create = AsyncMock(return_value=fake_msg)

    drafter = Drafter(profile, client=fake_client)
    result = await drafter.draft("Looking for UI designer", "landing", "en")

    assert "Hi!" in result
    fake_client.messages.create.assert_awaited_once()
    call_kwargs = fake_client.messages.create.call_args.kwargs
    assert "designer" in call_kwargs["system"].lower()
    assert "Looking for UI designer" in call_kwargs["messages"][0]["content"]
