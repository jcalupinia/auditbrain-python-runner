"""Tests del endpoint HTTP del Motor de balances (AUD, require_staff)."""

import io
import uuid

from openpyxl import Workbook

from backend.app.auth import service as auth_service
from backend.app.auth.models import Role
from backend.app.db.session import SessionLocal, init_db

BASE = "/api/v1/aud/motor-balances"


def _xlsx_crudo():
    wb = Workbook()
    ws = wb.active
    ws.append(["Código", "Cuenta", 2024])
    ws.append(["1.01", "Caja", 100.0])
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def _mk_user(role=Role.user):
    init_db()
    tag = uuid.uuid4().hex[:6]
    email = f"mb-{tag}@ex.com"
    pw = "Sup3rSecret!"
    db = SessionLocal()
    try:
        auth_service.create_user(db, email=email, password=pw, role=role)
    finally:
        db.close()
    return email, pw


def _login(client, email, pw):
    r = client.post("/api/v1/auth/login", data={"username": email, "password": pw})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def test_homologar_sin_auth_rechazado(client):
    r = client.post(
        f"{BASE}/homologar",
        files=[("archivos", ("b.xlsx", _xlsx_crudo(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))],
    )
    assert r.status_code in (401, 403), r.text


def test_homologar_con_staff_devuelve_esf_eri(client):
    email, pw = _mk_user(Role.user)  # rol operador = staff
    tok = _login(client, email, pw)
    r = client.post(
        f"{BASE}/homologar",
        headers=_h(tok),
        files=[("archivos", ("b.xlsx", _xlsx_crudo(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))],
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "esf" in body
    assert "eri" in body


def test_estados_con_staff_devuelve_lineas(client):
    email, pw = _mk_user(Role.user)
    tok = _login(client, email, pw)
    payload = {
        "esf": {"periodos": ["2024"], "filas": [
            {"cuenta": "x", "super_cias": "1010101", "es_hoja": True, "saldos": {"2024": 100.0}},
        ]},
        "eri": {"periodos": [], "filas": []},
    }
    r = client.post(f"{BASE}/estados", headers=_h(tok), json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "esf" in body
    assert "lineas" in body["esf"]


def test_plan_con_staff_devuelve_mapa(client):
    email, pw = _mk_user(Role.user)
    tok = _login(client, email, pw)
    r = client.get(f"{BASE}/plan", headers=_h(tok))
    assert r.status_code == 200, r.text
    body = r.json()
    assert "super_a_sri" in body
    assert "nombre_super" in body


def test_estados_sin_auth_rechazado(client):
    r = client.post(f"{BASE}/estados", json={"esf": {"periodos": [], "filas": []},
                                             "eri": {"periodos": [], "filas": []}})
    assert r.status_code in (401, 403), r.text


def test_plan_sin_auth_rechazado(client):
    r = client.get(f"{BASE}/plan")
    assert r.status_code in (401, 403), r.text
