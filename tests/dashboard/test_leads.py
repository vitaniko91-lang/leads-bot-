async def test_list_leads_default(client, basic_auth_header, seeded):
    r = await client.get("/api/leads", headers=basic_auth_header)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3
    assert data["items"][0]["id"] == seeded["lead_ids"][2]


async def test_list_leads_filter_by_status(client, basic_auth_header, seeded):
    r = await client.get("/api/leads?status=sent", headers=basic_auth_header)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["status"] == "sent"


async def test_list_leads_filter_by_min_score(client, basic_auth_header, seeded):
    r = await client.get("/api/leads?min_score=80", headers=basic_auth_header)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["relevance_score"] >= 80


async def test_list_leads_pagination(client, basic_auth_header, seeded):
    r = await client.get("/api/leads?limit=2&offset=0", headers=basic_auth_header)
    assert r.status_code == 200
    assert len(r.json()["items"]) == 2
    r = await client.get("/api/leads?limit=2&offset=2", headers=basic_auth_header)
    assert len(r.json()["items"]) == 1


async def test_lead_detail(client, basic_auth_header, seeded):
    lid = seeded["lead_ids"][0]
    r = await client.get(f"/api/leads/{lid}", headers=basic_auth_header)
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == lid
    assert "responses" in data
    assert len(data["responses"]) == 1
    assert data["responses"][0]["status"] == "sent"


async def test_lead_detail_404(client, basic_auth_header):
    r = await client.get("/api/leads/9999", headers=basic_auth_header)
    assert r.status_code == 404


async def test_patch_lead_updates_notes_and_client_status(
    client, basic_auth_header, seeded, session_factory,
):
    lid = seeded["lead_ids"][0]
    r = await client.patch(
        f"/api/leads/{lid}",
        json={"notes": "called back", "client_status": "in_work"},
        headers=basic_auth_header,
    )
    assert r.status_code == 200
    from sqlalchemy import select

    from leads_bot.db.models import Response
    async with session_factory() as s:
        resp = (await s.execute(
            select(Response).where(Response.lead_id == lid)
        )).scalar_one()
        assert resp.notes == "called back"
        assert resp.client_status == "in_work"


async def test_patch_lead_without_response_creates_no_op(
    client, basic_auth_header, seeded,
):
    lid = seeded["lead_ids"][2]
    r = await client.patch(
        f"/api/leads/{lid}",
        json={"notes": "x"},
        headers=basic_auth_header,
    )
    assert r.status_code == 404
