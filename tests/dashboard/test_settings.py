import json


async def test_get_settings_returns_defaults_when_file_absent(client, basic_auth_header):
    r = await client.get("/api/settings", headers=basic_auth_header)
    assert r.status_code == 200
    d = r.json()
    assert d["quiet_hours"] == "23:00-08:00"
    assert d["min_budget_usd"] == 300


async def test_patch_settings_persists(client, basic_auth_header, tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from leads_bot import config
    config._settings = None

    r = await client.patch("/api/settings", headers=basic_auth_header, json={
        "quiet_hours": "22:00-07:00",
        "min_budget_usd": 500,
        "min_relevance_score": 70,
        "max_responses_per_hour": 4,
        "max_responses_per_day": 20,
        "max_responses_per_week": 100,
    })
    assert r.status_code == 200
    p = tmp_path / "settings.json"
    data = json.loads(p.read_text())
    assert data["min_budget_usd"] == 500
    assert data["quiet_hours"] == "22:00-07:00"


async def test_patch_invalid_quiet_hours_422(client, basic_auth_header):
    r = await client.patch("/api/settings", headers=basic_auth_header, json={
        "quiet_hours": "garbage",
        "min_budget_usd": 500,
        "min_relevance_score": 70,
        "max_responses_per_hour": 4,
        "max_responses_per_day": 20,
        "max_responses_per_week": 100,
    })
    assert r.status_code == 422
