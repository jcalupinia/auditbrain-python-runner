"""Subida incremental de archivos por slot (chips del workspace)."""

import io
import uuid

import pytest

from tests.test_aud_of_router import _h, _login, _mk_admin_project  # noqa: F401
from tests.test_aud_of_router import _db  # noqa: F401


def _crear_borrador(client):
    tok, pid = _mk_admin_project(client)
    r = client.post(
        "/api/v1/aud/obligaciones-fiscales/jobs",
        headers=_h(tok),
        data={"project_id": pid, "cliente_name": "C", "period_label": "2025"},
    )
    return tok, r.json()["id"]


def _pdf():
    return ("d.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")


def _mk_admin_otra_organizacion(client):
    """Crea un admin en una organización DISTINTA a la del default compartido.

    ``_mk_admin_project`` no sirve para simular aislamiento entre
    organizaciones: todo usuario nuevo cae en la organización por defecto
    (``ensure_user_has_organization`` → ``get_or_create_default_organization``)
    y los operadores (admin/user) tienen acceso a cualquier proyecto de SU
    organización, así que dos llamadas a ``_mk_admin_project`` terminan en la
    MISMA organización. Para probar aislamiento real hay que asignar una
    organización nueva a mano, igual que hace
    ``tests/test_aud_of_service.py::test_create_job_no_access_raises``.
    """
    from backend.app.auth import service as auth_service
    from backend.app.auth.models import Role
    from backend.app.context.models import Organization
    from backend.app.db.session import SessionLocal

    tag = uuid.uuid4().hex[:6]
    email, pw = f"o-{tag}@ex.com", "Sup3rSecret!"
    db = SessionLocal()
    try:
        org = Organization(name=f"OrgB-{tag}", slug=f"orgb-{tag}")
        db.add(org)
        db.commit()
        db.refresh(org)
        u = auth_service.create_user(db, email=email, password=pw, role=Role.admin)
        u.organization_id = org.id
        db.add(u)
        db.commit()
    finally:
        db.close()
    return _login(client, email, pw)


def test_subir_un_pdf_al_slot_f104(client):
    tok, jid = _crear_borrador(client)
    r = client.put(
        f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/slots/f104",
        headers=_h(tok), files=[("archivos", _pdf())],
    )
    assert r.status_code == 200, r.text
    assert r.json()["f104"]["n_archivos"] == 1


def test_subir_dos_veces_al_mismo_slot_acumula(client):
    tok, jid = _crear_borrador(client)
    url = f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/slots/f104"
    client.put(url, headers=_h(tok), files=[("archivos", ("a.pdf", io.BytesIO(b"%PDF a"), "application/pdf"))])
    r = client.put(url, headers=_h(tok), files=[("archivos", ("b.pdf", io.BytesIO(b"%PDF b"), "application/pdf"))])
    assert r.json()["f104"]["n_archivos"] == 2


def test_quitar_un_slot_lo_deja_vacio(client):
    tok, jid = _crear_borrador(client)
    url = f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/slots/f104"
    client.put(url, headers=_h(tok), files=[("archivos", _pdf())])
    r = client.delete(url, headers=_h(tok))
    assert r.status_code == 200
    assert r.json()["f104"]["n_archivos"] == 0


def test_el_estado_de_los_slots_sobrevive_a_una_recarga(client):
    tok, jid = _crear_borrador(client)
    client.put(
        f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/slots/f104",
        headers=_h(tok), files=[("archivos", _pdf())],
    )
    r = client.get(f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/slots", headers=_h(tok))
    assert r.status_code == 200
    assert r.json()["f104"]["n_archivos"] == 1
    assert r.json()["f103"]["n_archivos"] == 0


def test_un_slot_inexistente_da_400(client):
    tok, jid = _crear_borrador(client)
    r = client.put(
        f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/slots/inventado",
        headers=_h(tok), files=[("archivos", _pdf())],
    )
    assert r.status_code == 400


def test_un_excel_en_el_slot_de_pdfs_es_rechazado(client):
    tok, jid = _crear_borrador(client)
    r = client.put(
        f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/slots/f104",
        headers=_h(tok),
        files=[("archivos", ("m.xlsx", io.BytesIO(b"PK"), "application/vnd.ms-excel"))],
    )
    assert r.status_code == 415


def test_el_mayor_especifico_exige_declarar_la_categoria(client):
    tok, jid = _crear_borrador(client)
    xlsx = ("m.xlsx", io.BytesIO(b"PK"),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    r = client.put(
        f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/slots/mayor_especifico",
        headers=_h(tok), files=[("archivos", xlsx)],
    )
    assert r.status_code == 400
    assert "categoria" in r.text.lower()


def test_el_mayor_especifico_guarda_la_categoria_declarada(client):
    tok, jid = _crear_borrador(client)
    xlsx = ("m.xlsx", io.BytesIO(b"PK"),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    r = client.put(
        f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/slots/mayor_especifico",
        headers=_h(tok), files=[("archivos", xlsx)], data={"categoria": "RET_IVA"},
    )
    assert r.status_code == 200
    r2 = client.get(f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}", headers=_h(tok))
    assert r2.json()["mayor_especifico_categoria"] == "RET_IVA"


def test_un_usuario_de_otra_organizacion_no_puede_subir_al_job(client):
    tok, jid = _crear_borrador(client)
    otro_tok = _mk_admin_otra_organizacion(client)
    r = client.put(
        f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/slots/f104",
        headers=_h(otro_tok), files=[("archivos", _pdf())],
    )
    assert r.status_code == 403
