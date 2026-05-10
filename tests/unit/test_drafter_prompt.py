import json
from pathlib import Path

import pytest

from leads_bot.drafter.profile import Profile, find_relevant_cases, load_profile
from leads_bot.drafter.prompts import DRAFTER_SYSTEM, build_drafter_prompt


@pytest.fixture
def profile_file(tmp_path: Path) -> Path:
    p = tmp_path / "profile.json"
    p.write_text(json.dumps({
        "name": "Vitalina",
        "portfolio_url": "https://x.design",
        "telegram": "@v",
        "min_rate_usd_per_hour": 50,
        "tone": "friendly",
        "payment_methods": ["wise", "payoneer"],
        "cases": [
            {"title": "Crypto landing", "tags": ["landing", "crypto"],
             "description": "x", "url": "u1"},
            {"title": "SaaS dashboard", "tags": ["app", "saas"],
             "description": "y", "url": "u2"},
            {"title": "Branding system", "tags": ["branding"],
             "description": "z", "url": "u3"},
        ],
    }))
    return p


def test_load_profile(profile_file):
    p = load_profile(profile_file)
    assert isinstance(p, Profile)
    assert p.name == "Vitalina"
    assert len(p.cases) == 3


def test_find_relevant_cases_by_project_type(profile_file):
    p = load_profile(profile_file)
    matches = find_relevant_cases(p, project_type="landing", limit=2)
    assert len(matches) >= 1
    assert any("landing" in c.tags for c in matches)


def test_find_relevant_cases_fallback_when_no_match(profile_file):
    p = load_profile(profile_file)
    matches = find_relevant_cases(p, project_type="other", limit=2)
    assert len(matches) == 2  # falls back to first N


def test_drafter_system_mentions_profile_aware():
    assert "designer" in DRAFTER_SYSTEM.lower()
    assert "tone" in DRAFTER_SYSTEM.lower()


def test_drafter_user_prompt_includes_lead_and_cases(profile_file):
    p = load_profile(profile_file)
    prompt = build_drafter_prompt(
        profile=p,
        lead_text="Looking for UI designer for crypto landing",
        project_type="landing",
        client_language="en",
    )
    assert "Looking for UI designer for crypto landing" in prompt
    assert "Crypto landing" in prompt
    assert "wise" in prompt.lower()
