from backend.app.notifications import email as email_mod


def test_render_confirmacion_substitutes_vars():
    html = email_mod.render_charla_confirmacion(
        nombre="María",
        titulo="Elaboración de Anexos Tributarios con Herramienta de Automatización",
        fecha="Jueves 18 de junio",
        hora="19h00 (Ecuador)",
        modalidad="Zoom",
        zoom_url="https://zoom.us/j/123",
    )
    assert "María" in html
    assert "Jueves 18 de junio" in html
    assert "https://zoom.us/j/123" in html
    assert "{{" not in html  # no quedan placeholders sin reemplazar


def test_render_confirmacion_without_zoom_url_no_button():
    html = email_mod.render_charla_confirmacion(
        nombre="María", titulo="T", fecha="F", hora="H", modalidad="Zoom", zoom_url=""
    )
    assert "{{" not in html
    assert "Unirme por Zoom" not in html


def test_send_confirmacion_calls_send_email(monkeypatch):
    captured = {}

    def fake_send_email(*, to, subject, html, max_retries=3):
        captured["to"] = to
        captured["subject"] = subject
        return {"id": "email_x"}

    monkeypatch.setattr(email_mod, "send_email", fake_send_email)
    out = email_mod.send_charla_confirmacion(
        to="maria@x.com", nombre="María", titulo="T",
        fecha="F", hora="H", modalidad="Zoom", zoom_url="",
    )
    assert out == {"id": "email_x"}
    assert captured["to"] == "maria@x.com"
    assert "T" in captured["subject"]


def test_render_confirmacion_with_group_and_data_protection():
    html = email_mod.render_charla_confirmacion(
        nombre="María",
        titulo="T",
        fecha="F",
        hora="H",
        modalidad="Zoom",
        zoom_url="",
        whatsapp_group_url="https://chat.whatsapp.com/ABC123",
        data_protection_contact="datos@auditconsulting.ec",
    )
    assert "https://chat.whatsapp.com/ABC123" in html
    assert "Unirme al grupo de WhatsApp" in html
    assert "Protección de Datos Personales" in html
    assert "datos@auditconsulting.ec" in html
    assert "{{" not in html


def test_send_aviso_interno_uses_env_recipient(monkeypatch):
    monkeypatch.setenv("EVENTS_NOTIFY_EMAIL", "firma@auditconsulting.ec")
    captured = {}

    def fake_send_email(*, to, subject, html, max_retries=3):
        captured["to"] = to
        return {"id": "x"}

    monkeypatch.setattr(email_mod, "send_email", fake_send_email)
    email_mod.send_charla_aviso_interno(
        nombre="María", email="maria@x.com", telefono="+593987654321",
        documento="1791240154001", empresa="Empresa S.A.", titulo="T",
    )
    assert captured["to"] == "firma@auditconsulting.ec"
