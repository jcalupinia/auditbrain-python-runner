def test_legacy_run_python_unchanged(client):
    """El endpoint legacy debe seguir funcionando sin API Key (auth gated
    desactivada por defecto) para no romper los GPTs existentes."""
    resp = client.post(
        "/run_python",
        json={"script": "result = {'Ingresos': 10000, 'Utilidad': 2500}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"] == {"Ingresos": 10000, "Utilidad": 2500}
    assert body["service"] == "AuditBrain Python Runner"
