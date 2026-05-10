async def test_health_does_not_require_auth(client):
    r = await client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_protected_endpoint_requires_auth(client):
    r = await client.get("/api/stats")
    assert r.status_code == 401
    assert "WWW-Authenticate" in r.headers


async def test_wrong_credentials_rejected(client, wrong_auth_header):
    r = await client.get("/api/stats", headers=wrong_auth_header)
    assert r.status_code == 401


async def test_correct_credentials_accepted(client, basic_auth_header):
    r = await client.get("/api/stats", headers=basic_auth_header)
    assert r.status_code == 200
