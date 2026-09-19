"""Tarea 5 del plan de Automatizaciones: correo con el enlace de acceso.

El correo NO lleva contraseña: el administrador la define él mismo con un
enlace de un solo uso. Y sale desde ``audit-ia.ec`` (dominio ya verificado en
Resend), sin mover el remitente del portal ni el de recursos.
"""

import pytest

from backend.app.notifications import email as email_mod


def test_render_reemplaza_los_cuatro_marcadores():
    html = email_mod.render_automatizacion_acceso(
        herramienta="Presupuestos con IA",
        empresa="Comercial Andina S.A.",
        enlace="https://presupuestos.audit-ia.ec/nueva-contrasena?token=abc123",
        contacto="info@auditconsulting.ec",
    )
    for marcador in ("{{herramienta}}", "{{empresa}}", "{{enlace}}", "{{contacto}}"):
        assert marcador not in html
    assert "Presupuestos con IA" in html
    assert "Comercial Andina S.A." in html or "Comercial Andina S.A." in html.replace(
        "&amp;", "&"
    )
    assert "token=abc123" in html
    assert "info@auditconsulting.ec" in html


def test_render_no_lleva_ninguna_clave():
    html = email_mod.render_automatizacion_acceso(
        herramienta="Presupuestos con IA",
        empresa="Comercial Andina S.A.",
        enlace="https://presupuestos.audit-ia.ec/nueva-contrasena?token=abc123",
        contacto="info@auditconsulting.ec",
    )
    bajo = html.lower()
    assert "contraseña:" not in bajo
    assert "clave:" not in bajo
    assert "{{clave}}" not in html
    # La promesa del texto: la define el propio administrador.
    assert "un solo uso" in bajo


class _Resp:
    status_code = 200

    @staticmethod
    def json():
        return {"id": "msg_1"}


@pytest.fixture()
def capturar_envio(monkeypatch):
    enviados = []

    def _post(url, headers=None, json=None, timeout=None):  # noqa: A002
        enviados.append(json)
        return _Resp()

    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.delenv("RESEND_FROM_EMAIL", raising=False)
    monkeypatch.delenv("RESEND_FROM_EMAIL_AUTOMATIZACIONES", raising=False)
    monkeypatch.setattr(email_mod.requests, "post", _post)
    return enviados


def test_send_automatizacion_acceso_usa_el_remitente_de_automatizaciones(capturar_envio):
    email_mod.send_automatizacion_acceso(
        to="admin@cliente.ec",
        herramienta="Presupuestos con IA",
        empresa="Comercial Andina S.A.",
        enlace="https://presupuestos.audit-ia.ec/nueva-contrasena?token=abc123",
        contacto="info@auditconsulting.ec",
    )
    assert len(capturar_envio) == 1
    assert capturar_envio[0]["from"] == "no-responder@audit-ia.ec"
    assert capturar_envio[0]["to"] == ["admin@cliente.ec"]


def test_remitente_de_automatizaciones_es_configurable(capturar_envio, monkeypatch):
    monkeypatch.setenv("RESEND_FROM_EMAIL_AUTOMATIZACIONES", "otro@audit-ia.ec")
    email_mod.send_automatizacion_acceso(
        to="admin@cliente.ec",
        herramienta="Presupuestos con IA",
        empresa="Comercial Andina S.A.",
        enlace="https://presupuestos.audit-ia.ec/nueva-contrasena?token=abc",
        contacto="info@auditconsulting.ec",
    )
    assert capturar_envio[0]["from"] == "otro@audit-ia.ec"


def test_los_demas_correos_siguen_con_el_remitente_de_siempre(capturar_envio):
    email_mod.send_email(to="alguien@example.com", subject="Hola", html="<p>hola</p>")
    email_mod.send_recurso_acceso(
        to="lead@example.com",
        titulo="Calculadora",
        enlace="https://recursos.audit-ia.ec/",
        clave="ABC123",
        contacto="info@auditconsulting.ec",
    )
    assert [m["from"] for m in capturar_envio] == [
        "no-reply@auditconsulting.com",
        "no-reply@auditconsulting.com",
    ]
