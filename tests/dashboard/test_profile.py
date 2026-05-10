import json
from pathlib import Path

import pytest


@pytest.fixture
def profile_path(tmp_path, monkeypatch) -> Path:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from leads_bot import config
    config._settings = None
    p = tmp_path / "profile.json"
    p.write_text(json.dumps({
        "name": "Vitalina",
        "portfolio_url": "https://x.design",
        "telegram": "@v",
        "min_rate_usd_per_hour": 50,
        "tone": "friendly",
        "payment_methods": ["wise"],
        "cases": [{"title": "Crypto", "tags": ["landing"], "description": "x", "url": "u"}],
    }))
    return p


async def test_get_profile(client, basic_auth_header, profile_path):
    r = await client.get("/api/profile", headers=basic_auth_header)
    assert r.status_code == 200
    assert r.json()["name"] == "Vitalina"


async def test_patch_profile_persists(client, basic_auth_header, profile_path):
    r = await client.patch("/api/profile", headers=basic_auth_header, json={
        "name": "Vita",
        "portfolio_url": "https://x.design",
        "telegram": "@v",
        "min_rate_usd_per_hour": 60,
        "tone": "direct",
        "payment_methods": ["wise", "payoneer"],
        "cases": [],
    })
    assert r.status_code == 200
    assert json.loads(profile_path.read_text())["min_rate_usd_per_hour"] == 60
    assert json.loads(profile_path.read_text())["tone"] == "direct"


async def test_get_profile_404_when_missing(
    client, basic_auth_header, tmp_path, monkeypatch,
):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from leads_bot import config
    config._settings = None
    r = await client.get("/api/profile", headers=basic_auth_header)
    assert r.status_code == 404
