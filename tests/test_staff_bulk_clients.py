"""Tests de la carga masiva de clientes (licencias) en bloque.

Regla de negocio (2026-06-26): UNA cuenta por correo único. Si varios clientes
comparten el mismo correo (contador), se crea una sola cuenta. Los correos
inválidos se OMITEN y se reportan. Los correos ya existentes no se duplican.
"""
import uuid
from io import BytesIO

import openpyxl
import pytest

from backend.app.auth.models import Role
from backend.app.auth.service import create_user, get_user_by_email
from backend.app.context.models import Organization
from backend.app.db.session import SessionLocal


@pytest.fixture()
def db_session():
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture()
def org(db_session):
    slug = f"bulk-{uuid.uuid4().hex[:6]}"
    o = Organization(name=f"ORG-{slug}", slug=slug, is_active=True)
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    return o


def _xlsx_bytes(rows):
    """rows: list of (cliente, ruc, email). Antepone fila vacía + encabezado."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append([None, None, None])
    ws.append(["CLIENTE", "RUC", "Email Contador"])
    for r in rows:
        ws.append(list(r))
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_parse_clients_workbook_skips_header_and_blanks():
    from backend.app.staff_portal.service import parse_clients_workbook
    data = _xlsx_bytes([
        ("EMPRESA A", "111", "a@x.com"),
        ("EMPRESA B", "222", "b@x.com"),
    ])
    rows = parse_clients_workbook(data)
    assert len(rows) == 2
    assert rows[0]["cliente"] == "EMPRESA A"
    assert rows[0]["ruc"] == "111"
    assert rows[0]["email"] == "a@x.com"


def test_bulk_creates_one_account_per_unique_email(db_session, org):
    from backend.app.staff_portal.service import bulk_create_portal_clients
    e = f"contador-{uuid.uuid4().hex[:6]}@x.com"
    rows = [
        {"cliente": "EMPRESA A", "ruc": "111", "email": e},
        {"cliente": "EMPRESA B", "ruc": "222", "email": e},  # mismo correo
    ]
    res = bulk_create_portal_clients(db_session, organization_id=org.id, rows=rows)
    assert len(res["creados"]) == 1, "Correo repetido → una sola cuenta"
    creado = res["creados"][0]
    assert creado["email"] == e
    assert creado["temp_password"]
    assert set(creado["empresas"]) == {"EMPRESA A", "EMPRESA B"}
    # El usuario existe y es rol client
    u = get_user_by_email(db_session, e)
    assert u is not None and u.role == Role.client


def test_bulk_extracts_embedded_email(db_session, org):
    """Extrae el correo aunque venga dentro de texto: 'Nombre <correo>',
    varios correos separados por ';' o salto de línea, o con comillas."""
    from backend.app.staff_portal.service import bulk_create_portal_clients
    uniq = uuid.uuid4().hex[:6]
    rows = [
        {"cliente": "CORPAL", "ruc": "1", "email": f"EDWIN ORTIZ <eortiz-{uniq}@corpal.com.ec>"},
        {"cliente": "LOGISINTER", "ruc": "2", "email": f"finance-{uniq}@outlook.com; contabilidad@choice.com"},
        {"cliente": "I&G", "ruc": "3", "email": f"gcontable-{uniq}@iyg.com.ec\ngfinanciera@iyg.com.ec"},
    ]
    res = bulk_create_portal_clients(db_session, organization_id=org.id, rows=rows)
    creados = {c["email"] for c in res["creados"]}
    assert f"eortiz-{uniq}@corpal.com.ec" in creados
    assert f"finance-{uniq}@outlook.com" in creados  # primer correo de la celda
    assert f"gcontable-{uniq}@iyg.com.ec" in creados
    assert len(res["omitidos"]) == 0


def test_password_is_domain_plus_ruc4(db_session, org):
    """La clave = dominio del correo (sin .com) + 4 primeros dígitos del RUC."""
    from backend.app.staff_portal.service import (
        bulk_create_portal_clients, password_from_email_ruc,
    )
    assert password_from_email_ruc("contador@corpogranja.com", "1792470013001") == "corpogranja1792"
    assert password_from_email_ruc("c.rivadeneira@sixt.ec", "1792995221001") == "sixt1792"

    uniq = uuid.uuid4().hex[:6]
    e = f"contador@{uniq}empresa.com"
    res = bulk_create_portal_clients(
        db_session, organization_id=org.id,
        rows=[{"cliente": "X", "ruc": "1391925220001", "email": e}],
    )
    assert res["creados"][0]["temp_password"] == f"{uniq}empresa1391"


def test_bulk_omits_invalid_emails(db_session, org):
    from backend.app.staff_portal.service import bulk_create_portal_clients
    rows = [
        {"cliente": "SIN CORREO", "ruc": "999", "email": "HACEMOS NOSOTROS"},
        {"cliente": "VACIO", "ruc": "888", "email": ""},
    ]
    res = bulk_create_portal_clients(db_session, organization_id=org.id, rows=rows)
    assert len(res["creados"]) == 0
    assert len(res["omitidos"]) == 2
    assert {o["cliente"] for o in res["omitidos"]} == {"SIN CORREO", "VACIO"}


def test_bulk_skips_already_existing_email(db_session, org):
    from backend.app.staff_portal.service import bulk_create_portal_clients
    e = f"ya-existe-{uuid.uuid4().hex[:6]}@x.com"
    create_user(db_session, email=e, password="Existe123!", role=Role.client)
    rows = [{"cliente": "DUP", "ruc": "111", "email": e}]
    res = bulk_create_portal_clients(db_session, organization_id=org.id, rows=rows)
    assert len(res["creados"]) == 0
    assert len(res["existentes"]) == 1
    assert res["existentes"][0]["email"] == e


def test_bulk_endpoint_creates_accounts(client, db_session, org):
    """E2E: POST /staff/portal-users/bulk con un Excel crea cuentas y reporta."""
    email_admin = f"admin-bulk-{uuid.uuid4().hex[:6]}@x.com"
    admin = create_user(db_session, email=email_admin, password="AdminBulk1!", role=Role.admin)
    admin.organization_id = org.id
    db_session.add(admin); db_session.commit()
    r = client.post(
        "/api/v1/auth/login", data={"username": email_admin, "password": "AdminBulk1!"}
    )
    tok = r.json()["access_token"]

    e = f"masivo-{uuid.uuid4().hex[:6]}@x.com"
    data = _xlsx_bytes([
        ("EMPRESA X", "111", e),
        ("EMPRESA Y", "222", e),            # mismo correo → 1 cuenta
        ("SIN MAIL", "333", "OUTSOURCING"),  # inválido → omitido
    ])
    resp = client.post(
        "/api/v1/staff/portal-users/bulk",
        headers={"Authorization": f"Bearer {tok}"},
        files={"file": ("clientes.xlsx", data,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["resumen"]["creados"] == 1
    assert body["resumen"]["omitidos"] == 1
    assert get_user_by_email(db_session, e) is not None


def test_bulk_endpoint_requires_admin(client, db_session):
    """Un usuario NO admin no puede usar la carga masiva."""
    e = f"user-{uuid.uuid4().hex[:6]}@x.com"
    create_user(db_session, email=e, password="User1234!", role=Role.user)
    r = client.post("/api/v1/auth/login", data={"username": e, "password": "User1234!"})
    tok = r.json()["access_token"]
    data = _xlsx_bytes([("A", "1", "a@x.com")])
    resp = client.post(
        "/api/v1/staff/portal-users/bulk",
        headers={"Authorization": f"Bearer {tok}"},
        files={"file": ("c.xlsx", data, "application/octet-stream")},
    )
    assert resp.status_code == 403


def test_list_all_portal_users_returns_clients(db_session, org):
    from backend.app.staff_portal.service import (
        bulk_create_portal_clients, list_all_portal_users,
    )
    e = f"listame-{uuid.uuid4().hex[:6]}@x.com"
    bulk_create_portal_clients(
        db_session, organization_id=org.id,
        rows=[{"cliente": "LISTA", "ruc": "111", "email": e}],
    )
    rows = list_all_portal_users(db_session)
    emails = {r["email"] for r in rows}
    assert e in emails
    row = next(r for r in rows if r["email"] == e)
    assert "id" in row and "is_active" in row and "cliente" in row
