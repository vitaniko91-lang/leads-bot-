async def test_stats_today_returns_kpis(client, basic_auth_header, seeded):
    r = await client.get("/api/stats?period=today", headers=basic_auth_header)
    assert r.status_code == 200
    data = r.json()
    assert set(data.keys()) >= {
        "period", "leads_total", "sent_count", "reply_count",
        "conversion_pct", "by_hour",
    }
    assert data["period"] == "today"
    assert isinstance(data["by_hour"], list)


async def test_stats_invalid_period_400(client, basic_auth_header):
    r = await client.get("/api/stats?period=forever", headers=basic_auth_header)
    assert r.status_code == 422


async def test_stats_week_aggregates(client, basic_auth_header, seeded):
    r = await client.get("/api/stats?period=week", headers=basic_auth_header)
    assert r.status_code == 200
    d = r.json()
    assert d["leads_total"] >= 0
    assert 0 <= d["conversion_pct"] <= 100
