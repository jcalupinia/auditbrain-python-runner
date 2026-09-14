import datetime
import uuid

from backend.app.db.session import SessionLocal
from backend.app.notifications import email as email_mod
from backend.app.recursos import notify
from backend.app.recursos.models import RecursoLead
from backend.app.recursos.tokens import leer_token

SLUG = "anticipo-ir-2026"


def test_render_sin_texto_de_usuario_e_incluye_enlace():
    html = email_mod.render_recurso_acceso(
        titulo="Calculadora del Anticipo IR 2026",
        email="ana@example.com",
        enlace="https://recursos.audit-ia.ec/anticipo-ir-2026/?acceso=abc&x=1",
        contacto="jcalupinia@auditconsulting.ec",
    )
    assert "Estimado(a):" in html
    assert 'href="https://recursos.audit-ia.ec/anticipo-ir-2026/?acceso=abc&amp;x=1"' in html
    assert "ana@example.com" in html
    assert "jcalupinia@auditconsulting.ec" in html


def test_notify_nombre_hostil_no_llega_al_correo(monkeypatch):
    enviados = []
    monkeypatch.setattr(
        email_mod, "send_recurso_acceso", lambda **kw: enviados.append(kw) or {"id": "re_1"}
    )
    db = SessionLocal()
    try:
        lead = RecursoLead(
            recurso_slug=SLUG,
            nombre="Su cuenta fue suspendida, llame al 0999",
            empresa="Alfa S.A.",
            email=f"n-{uuid.uuid4().hex[:8]}@example.com",
            consentimiento_at=datetime.datetime(2026, 9, 14),
            consentimiento_version="v1",
        )
        db.add(lead)
        db.commit()
        lead_id = lead.id
    finally:
        db.close()

    notify.enviar_acceso(lead_id)

    assert len(enviados) == 1
    kw = enviados[0]
    assert "nombre" not in kw
    html = email_mod.render_recurso_acceso(**{k: v for k, v in kw.items() if k != "to"}, email=kw["to"])
    assert "suspendida" not in html
    assert "0999" not in html


def test_notify_envia_enlace_valido_y_marca_enviado(monkeypatch):
    db = SessionLocal()
    try:
        lead = RecursoLead(
            recurso_slug=SLUG,
            nombre="Ana Torres",
            empresa="Alfa S.A.",
            email=f"n-{uuid.uuid4().hex[:8]}@example.com",
            consentimiento_at=datetime.datetime(2026, 9, 14),
            consentimiento_version="v1",
        )
        db.add(lead)
        db.commit()
        lead_id, correo = lead.id, lead.email
    finally:
        db.close()

    enviados = []
    monkeypatch.setattr(
        email_mod, "send_recurso_acceso", lambda **kw: enviados.append(kw) or {"id": "re_1"}
    )
    notify.enviar_acceso(lead_id)

    assert len(enviados) == 1
    kw = enviados[0]
    assert kw["to"] == correo
    prefijo = "https://recursos.audit-ia.ec/anticipo-ir-2026/?acceso="
    assert kw["enlace"].startswith(prefijo)
    assert leer_token(kw["enlace"][len(prefijo):], SLUG) == lead_id

    db = SessionLocal()
    try:
        assert db.get(RecursoLead, lead_id).email_enviado is True
    finally:
        db.close()


def test_notify_lead_inexistente_no_falla(monkeypatch):
    monkeypatch.setattr(email_mod, "send_recurso_acceso", lambda **kw: 1 / 0)
    notify.enviar_acceso(999_999_999)  # no debe lanzar


def test_notify_envio_fallido_no_regresa_email_enviado_a_false(monkeypatch):
    db = SessionLocal()
    try:
        lead = RecursoLead(
            recurso_slug=SLUG,
            nombre="Ana Torres",
            empresa="Alfa S.A.",
            email=f"n-{uuid.uuid4().hex[:8]}@example.com",
            consentimiento_at=datetime.datetime(2026, 9, 14),
            consentimiento_version="v1",
            email_enviado=True,
        )
        db.add(lead)
        db.commit()
        lead_id = lead.id
    finally:
        db.close()

    monkeypatch.setattr(email_mod, "send_recurso_acceso", lambda **kw: None)
    notify.enviar_acceso(lead_id)

    db = SessionLocal()
    try:
        assert db.get(RecursoLead, lead_id).email_enviado is True
    finally:
        db.close()
