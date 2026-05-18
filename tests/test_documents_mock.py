from backend.app.document_services import universal_document_client


class _FakeResponse:
    status_code = 200
    text = ""

    def json(self):
        return {"url": "https://example.com/doc.pdf"}


def test_documents_generate_mock(client, monkeypatch):
    monkeypatch.setattr(
        universal_document_client.requests,
        "post",
        lambda *a, **k: _FakeResponse(),
    )
    resp = client.post(
        "/api/v1/documents/generate",
        json={
            "result": {"Ingresos": 1000},
            "output_expectations": {"format": "pdf"},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["response"]["url"].endswith("doc.pdf")
