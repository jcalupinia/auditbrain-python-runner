import datetime
import uuid

from backend.app.db.session import SessionLocal
from backend.app.notifications import email as email_mod
from backend.app.recursos import notify
from backend.app.recursos.models import RecursoCuenta, RecursoLead

SLUG = "ir-personas-naturales-2026"


def test_render_muestra_usuario_clave_y_boton():
    html = email_mod.render_recurso_acceso(
        titulo="Calculadora de Impuesto a la Renta de Personas Naturales 2026",
        email="ana@example.com",
        enlace="https://recursos.audit-ia.ec/ir-personas-naturales-2026/?x=1&y=2",
        clave="ABC-DEF-GHJ",
        contacto="jcalupinia@auditconsulting.ec",
    )
    assert "ana@example.com" in html
    assert "ABC-DEF-GHJ" in html
    assert "monospace" in html
    assert "Ingresar a mi calculadora" in html
    assert 'href="https://recursos.audit-ia.ec/ir-personas-naturales-2026/?x=1&amp;y=2"' in html
    assert "¿Olvidó su clave?" in html
    assert "jcalupinia@auditconsulting.ec" in html
    assert "{{" not in html


def test_render_escapa_todo():
    html = email_mod.render_recurso_acceso(
        titulo="<b>T</b>", email="a<x>@example.com", enlace='https://e/"x', clave="<c>", contacto="<k>"
    )
    for crudo in ("<b>T</b>", "<x>", '"x', "<c>", "<k>"):
        assert crudo not in html


def test_send_asunto_y_reintentos(monkeypatch):
    llamadas = []
    monkeypatch.setattr(email_mod, "send_email", lambda **kw: llamadas.append(kw) or {"id": "re_1"})
    email_mod.send_recurso_acceso(
        to="ana@example.com", titulo="Calc X", enlace="https://e/", clave="ABC-DEF-GHJ", contacto="c@e.ec"
    )
    [kw] = llamadas
    assert kw["subject"] == "Su usuario y clave — Calc X"
    assert kw["max_retries"] == 2
    assert "ABC-DEF-GHJ" in kw["html"]


def _cuenta_y_lead(nombre="Ana Torres", email_enviado=False):
    email = f"n-{uuid.uuid4().hex[:8]}@example.com"
    db = SessionLocal()
    try:
        db.add(
            RecursoLead(
                recurso_slug=SLUG, nombre=nombre, empresa="Alfa S.A.", email=email,
                consentimiento_at=datetime.datetime(2026, 9, 14), consentimiento_version="v1",
                email_enviado=email_enviado,
            )
        )
        cuenta = RecursoCuenta(email=email, hashed_clave="x", clave_generada=True)
        db.add(cuenta)
        db.commit()
        return cuenta.id, email
    finally:
        db.close()


def _lead_enviado(email):
    db = SessionLocal()
    try:
        return db.query(RecursoLead).filter_by(email=email).one().email_enviado
    finally:
        db.close()


def test_notify_envia_clave_y_marca_enviado_sin_texto_de_usuario(monkeypatch):
    cuenta_id, correo = _cuenta_y_lead(nombre="Su cuenta fue suspendida, llame al 0999")
    enviados = []
    monkeypatch.setattr(
        email_mod, "send_recurso_acceso", lambda **kw: enviados.append(kw) or {"id": "re_1"}
    )
    notify.enviar_clave(cuenta_id, "ABC-DEF-GHJ", SLUG)

    [kw] = enviados
    assert kw == {
        "to": correo,
        "titulo": "Calculadora de Impuesto a la Renta de Personas Naturales 2026",
        "enlace": "https://recursos.audit-ia.ec/ir-personas-naturales-2026/",
        "clave": "ABC-DEF-GHJ",
        "contacto": "jcalupinia@auditconsulting.ec",
    }
    html = email_mod.render_recurso_acceso(**{k: v for k, v in kw.items() if k != "to"}, email=kw["to"])
    assert "suspendida" not in html and "0999" not in html.replace("0990 609 811", "")
    assert _lead_enviado(correo) is True


def test_notify_cuenta_inexistente_no_falla(monkeypatch):
    monkeypatch.setattr(email_mod, "send_recurso_acceso", lambda **kw: 1 / 0)
    notify.enviar_clave(999_999_999, "ABC-DEF-GHJ", SLUG)  # no debe lanzar


def test_notify_excepcion_no_propaga_ni_registra_clave(monkeypatch, caplog):
    cuenta_id, _ = _cuenta_y_lead()
    monkeypatch.setattr(email_mod, "send_recurso_acceso", lambda **kw: 1 / 0)
    notify.enviar_clave(cuenta_id, "ABC-DEF-GHJ", SLUG)
    assert "ABC-DEF-GHJ" not in caplog.text


def test_notify_envio_fallido_no_regresa_email_enviado_a_false(monkeypatch):
    cuenta_id, correo = _cuenta_y_lead(email_enviado=True)
    monkeypatch.setattr(email_mod, "send_recurso_acceso", lambda **kw: None)
    notify.enviar_clave(cuenta_id, "ABC-DEF-GHJ", SLUG)
    assert _lead_enviado(correo) is True
