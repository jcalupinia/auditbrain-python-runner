def test_python_run_v1(client):
    resp = client.post(
        "/api/v1/python/run",
        json={"script": "result = {'a': 1 + 1}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"] == {"a": 2}
    assert body["service"] == "AuditBrain Platform v1 - python_runner"


def test_python_run_empty_script(client):
    resp = client.post("/api/v1/python/run", json={"script": ""})
    assert resp.status_code == 200
    assert "error" in resp.json()
