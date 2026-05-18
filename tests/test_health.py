def test_platform_health(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "AuditBrain Platform v1"
    assert "auth_enabled" in body


def test_legacy_root_still_works(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["service"] == "AuditBrain Python Runner"
