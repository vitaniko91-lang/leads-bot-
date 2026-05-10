async def test_list_sources_returns_metrics(client, basic_auth_header, seeded):
    r = await client.get("/api/sources", headers=basic_auth_header)
    assert r.status_code == 200
    data = r.json()
    assert len(data["items"]) == 1
    s = data["items"][0]
    assert s["title"] == "Design Jobs UA"
    assert "leads_per_day" in s
    assert "sent_per_day" in s
    assert "conversion_pct" in s


async def test_pause_source(client, basic_auth_header, seeded, session_factory):
    sid = seeded["source_id"]
    r = await client.patch(
        f"/api/sources/{sid}",
        json={"status": "paused"},
        headers=basic_auth_header,
    )
    assert r.status_code == 200
    from sqlalchemy import select

    from leads_bot.db.models import Source
    async with session_factory() as s:
        src = (await s.execute(select(Source).where(Source.id == sid))).scalar_one()
        assert src.status == "paused"


async def test_mute_source_for_minutes(client, basic_auth_header, seeded, session_factory):
    sid = seeded["source_id"]
    r = await client.patch(
        f"/api/sources/{sid}",
        json={"mute_for_minutes": 60},
        headers=basic_auth_header,
    )
    assert r.status_code == 200
    from datetime import datetime

    from sqlalchemy import select

    from leads_bot.db.models import Source
    async with session_factory() as s:
        src = (await s.execute(select(Source).where(Source.id == sid))).scalar_one()
        assert src.muted_until is not None
        assert src.muted_until > datetime.utcnow()


async def test_patch_source_404(client, basic_auth_header):
    r = await client.patch(
        "/api/sources/9999", json={"status": "paused"},
        headers=basic_auth_header,
    )
    assert r.status_code == 404
