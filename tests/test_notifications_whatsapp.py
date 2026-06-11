from backend.app.notifications import whatsapp as wa


def test_no_config_returns_none(monkeypatch):
    for var in ("WHATSAPP_TOKEN", "WHATSAPP_PHONE_NUMBER_ID", "WHATSAPP_TEMPLATE_NAME"):
        monkeypatch.delenv(var, raising=False)
    result = wa.send_template_message(to_e164="+593987654321", variables=["María"])
    assert result is None


def test_builds_template_body(monkeypatch):
    monkeypatch.setenv("WHATSAPP_TOKEN", "tok")
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "12345")
    monkeypatch.setenv("WHATSAPP_TEMPLATE_NAME", "confirmacion_charla")
    monkeypatch.setenv("WHATSAPP_TEMPLATE_LANG", "es")

    captured = {}

    class _Resp:
        status_code = 200

        def json(self):
            return {"messages": [{"id": "wamid.x"}]}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return _Resp()

    monkeypatch.setattr(wa.requests, "post", fake_post)

    result = wa.send_template_message(
        to_e164="+593987654321", variables=["María", "Jueves 18 de junio", "19h00"]
    )
    assert result == {"messages": [{"id": "wamid.x"}]}
    assert "12345/messages" in captured["url"]
    assert captured["json"]["to"] == "593987654321"
    assert captured["json"]["type"] == "template"
    assert captured["json"]["template"]["name"] == "confirmacion_charla"
    params = captured["json"]["template"]["components"][0]["parameters"]
    assert [p["text"] for p in params] == ["María", "Jueves 18 de junio", "19h00"]
