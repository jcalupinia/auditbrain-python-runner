def test_router_python_runner(client):
    resp = client.post(
        "/api/v1/router/execute",
        json={"target": "python_runner", "payload": {"script": "result = 21 * 2"}},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["target"] == "python_runner"
    assert body["result"]["result"] == 42


def test_router_future_module_not_implemented(client):
    resp = client.post(
        "/api/v1/router/execute",
        json={"target": "future_tax_module", "payload": {}},
    )
    assert resp.status_code == 501


def test_router_unknown_target(client):
    resp = client.post(
        "/api/v1/router/execute",
        json={"target": "nope", "payload": {}},
    )
    assert resp.status_code == 400
