"""El correo de acceso de AUDIT SOUND usa su propia plantilla (no la de Recursos)."""
from backend.app.notifications import email as email_svc


def test_render_correo_audit_sound_marca_y_boton():
    html = email_svc.render_app_account_access(
        email="dj@x.com", clave="LcBSX27WiSSr5t",
        enlace="https://sound.audit-ia.ec/pro/login.html",
        contacto="info@auditconsulting.ec",
    )
    # Marca y contenido correctos
    assert "AUDIT" in html and "SOUND" in html
    assert "Ingresar a AUDIT SOUND" in html
    assert "Su usuario y clave" in html
    assert "dj@x.com" in html and "LcBSX27WiSSr5t" in html
    assert "https://sound.audit-ia.ec/pro/login.html" in html
    # NO debe arrastrar nada de Recursos
    assert "Recursos gratuitos" not in html
    assert "calculadora" not in html
    assert "logo-auditconsulting" not in html


def test_render_correo_logo_opcional():
    sin = email_svc.render_app_account_access(
        email="d@x.com", clave="Clave1234", enlace="https://x/login", contacto="a@b.c",
    )
    assert "{{logo_block}}" not in sin and "<img" not in sin  # sin logo configurado
    con = email_svc.render_app_account_access(
        email="d@x.com", clave="Clave1234", enlace="https://x/login", contacto="a@b.c",
        logo_url="https://sound.audit-ia.ec/pro/assets/logo_audit_ia.jpg",
    )
    assert '<img src="https://sound.audit-ia.ec/pro/assets/logo_audit_ia.jpg"' in con


def test_send_usa_la_plantilla_propia(monkeypatch):
    captured = {}
    monkeypatch.setattr(email_svc, "send_email", lambda **kw: captured.update(kw) or {"id": "x"})
    email_svc.send_app_account_access(to="dj@x.com", clave="Clave1234")
    assert captured["subject"] == "Su usuario y clave — AUDIT SOUND"
    assert "Ingresar a AUDIT SOUND" in captured["html"]
    assert "Recursos gratuitos" not in captured["html"]
