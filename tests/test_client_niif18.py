"""NIIF 18 Studio del portal cliente: acceso, normativa y modelos de las firmas.

Lo que se protege aquí es la regla comercial y de licencia del módulo:

* Sin sesión no se entrega nada.
* Un `client` necesita el entitlement ``NIIF_18_STUDIO``.
* Un `client` ve la normativa NIIF pero **nunca** los modelos de EY, KPMG, PwC,
  Deloitte y Grant Thornton: ni el PDF, ni la lista, ni sus nombres en el
  manifiesto. El bloqueo es del servidor, no de la vista.
* Un operador (`admin`/`user`) sí los ve.
* No hay forma de alcanzar los PDF por la ruta de la biblioteca ni por
  *path traversal*.
"""
import json
import uuid

import pytest

from backend.app.auth.jwt_tokens import create_access_token
from backend.app.auth.models import Role
from backend.app.auth.service import create_user, get_user_by_email
from backend.app.client_portal import entitlements as ent
from backend.app.client_portal.service import create_portal_user
from backend.app.context.models import Client, Organization
from backend.app.db.session import SessionLocal

TOOL = "NIIF_18_STUDIO"


@pytest.fixture()
def db_session():
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture()
def admin_headers(db_session):
    """Operador (admin) del Command Center, que entra al portal con su usuario."""
    email = f"op-n18-{uuid.uuid4().hex[:8]}@example.com"
    u = get_user_by_email(db_session, email) or create_user(
        db_session, email=email, password="x", role=Role.admin
    )
    return {"Authorization": f"Bearer {create_access_token(subject=u.email, role='admin')}"}


@pytest.fixture()
def biblioteca(tmp_path, monkeypatch):
    """Biblioteca mínima en disco, con la misma forma que la real."""
    libro = tmp_path / "libro"
    (libro / "normas").mkdir(parents=True)
    (libro / "modelos-niif18").mkdir()
    (libro / "modelos-2026").mkdir()
    (libro / "index.html").write_text("<h1>Índice</h1>", encoding="utf-8")
    (libro / "normas" / "ifrs18.html").write_text("<h1>NIIF 18</h1>", encoding="utf-8")
    (libro / "normas" / "ifrs18-ie.html").write_text("<h1>Ejemplos</h1>", encoding="utf-8")
    (libro / "modelos-niif18" / "EY_GoodGroup.pdf").write_bytes(b"%PDF-1.4 ey")
    (libro / "modelos-2026" / "KPMG_2026.pdf").write_bytes(b"%PDF-1.4 kpmg")
    (tmp_path / "manifiesto.json").write_text(
        json.dumps(
            {
                "totales": {"normas": 1, "ejemplos": 1, "modelos": 2},
                "destacado": [{"titulo": "NIIF 18", "href": "libro/normas/ifrs18.html"}],
                "secciones": [
                    {
                        "titulo": "NIIF",
                        "items": [
                            {
                                "etiqueta": "NIIF 18",
                                "nombre": "Presentación",
                                "href": "libro/normas/ifrs18.html",
                                "ejemplos": {
                                    "href": "libro/normas/ifrs18-ie.html",
                                    "texto": "Ejemplos ilustrativos",
                                },
                            }
                        ],
                    }
                ],
                "modelos": [
                    {
                        "grupo": "modelos-niif18",
                        "archivo": "EY_GoodGroup.pdf",
                        "titulo": "EY — Good Group",
                        "firma": "EY",
                        "url": "/modelos/modelos-niif18/EY_GoodGroup.pdf",
                    },
                    {
                        "grupo": "modelos-2026",
                        "archivo": "KPMG_2026.pdf",
                        "titulo": "KPMG — 2026",
                        "firma": "KPMG",
                        "url": "/modelos/modelos-2026/KPMG_2026.pdf",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("NIIF18_BIBLIOTECA_DIR", str(libro))
    return libro


def _login_cliente(client, db, *, conceder=True):
    suf = uuid.uuid4().hex[:8]
    org = Organization(name=f"ORG-{suf}", slug=f"org-{suf}", is_active=True)
    db.add(org); db.commit(); db.refresh(org)
    cli = Client(organization_id=org.id, name=f"CL-{suf}", is_active=True)
    db.add(cli); db.commit(); db.refresh(cli)
    user, pwd = create_portal_user(db, client_id=cli.id, email=f"n18-{suf}@example.com")
    if conceder:
        ent.set_user_entitlements(db, user.id, {TOOL})
    r = client.post("/api/v1/client/auth/login", data={"username": user.email, "password": pwd})
    assert r.status_code == 200, r.text
    tok = r.json()["access_token"]
    dev = r.cookies.get("device_id")
    return {"headers": {"Authorization": f"Bearer {tok}"},
            "cookies": {"device_id": dev} if dev else {}}


# ---------------------------------------------------------------- sin sesión
def test_sin_sesion_no_se_entrega_nada(client, biblioteca):
    for ruta in (
        "/api/v1/client/niif18/me",
        "/api/v1/client/niif18/normas",
        "/api/v1/client/niif18/biblioteca/index.html",
        "/api/v1/client/niif18/modelos/modelos-niif18/EY_GoodGroup.pdf",
    ):
        r = client.get(ruta)
        assert r.status_code in (401, 403), f"{ruta} devolvió {r.status_code}"


# ---------------------------------------------------------------- entitlement
def test_cliente_sin_entitlement_queda_fuera(client, db_session, biblioteca):
    auth = _login_cliente(client, db_session, conceder=False)
    r = client.get("/api/v1/client/niif18/me", **auth)
    assert r.status_code == 403


def test_cliente_con_entitlement_entra_y_ve_su_rol(client, db_session, biblioteca):
    auth = _login_cliente(client, db_session)
    r = client.get("/api/v1/client/niif18/me", **auth)
    assert r.status_code == 200
    u = r.json()["usuario"]
    assert u["rol"] == "client"
    assert u["operador"] is False


# ---------------------------------------------------------------- normativa
def test_cliente_abre_las_normas(client, db_session, biblioteca):
    auth = _login_cliente(client, db_session)
    r = client.get("/api/v1/client/niif18/biblioteca/index.html", **auth)
    assert r.status_code == 200
    assert "Índice" in r.text

    r = client.get("/api/v1/client/niif18/biblioteca/normas/ifrs18.html", **auth)
    assert r.status_code == 200
    assert "NIIF 18" in r.text


def test_el_manifiesto_del_cliente_no_nombra_los_modelos(client, db_session, biblioteca):
    """Un cliente no debe conocer ni los nombres de los archivos de las firmas."""
    auth = _login_cliente(client, db_session)
    r = client.get("/api/v1/client/niif18/normas", **auth)
    assert r.status_code == 200
    datos = r.json()
    assert datos["modelos"] == []
    crudo = json.dumps(datos)
    for rastro in ("EY_GoodGroup", "KPMG_2026", "Deloitte", "Grant Thornton"):
        assert rastro not in crudo


# ---------------------------------------------------------------- modelos
def test_cliente_no_descarga_los_modelos_de_las_firmas(client, db_session, biblioteca):
    auth = _login_cliente(client, db_session)
    for ruta in (
        "/api/v1/client/niif18/modelos",
        "/api/v1/client/niif18/modelos/modelos-niif18/EY_GoodGroup.pdf",
        "/api/v1/client/niif18/modelos/modelos-2026/KPMG_2026.pdf",
    ):
        r = client.get(ruta, **auth)
        assert r.status_code == 403, f"{ruta} devolvió {r.status_code}"


def test_la_ruta_de_biblioteca_no_alcanza_los_modelos(client, db_session, biblioteca):
    """Aunque se conozca el nombre, por /biblioteca/ nunca se entregan."""
    auth = _login_cliente(client, db_session)
    for ruta in (
        "/api/v1/client/niif18/biblioteca/modelos-niif18/EY_GoodGroup.pdf",
        "/api/v1/client/niif18/biblioteca/modelos-2026/KPMG_2026.pdf",
    ):
        r = client.get(ruta, **auth)
        assert r.status_code == 403, f"{ruta} devolvió {r.status_code}"


def test_no_hay_escape_por_path_traversal(client, db_session, biblioteca):
    auth = _login_cliente(client, db_session)
    for ruta in (
        "/api/v1/client/niif18/biblioteca/../manifiesto.json",
        "/api/v1/client/niif18/biblioteca/normas/../../manifiesto.json",
        "/api/v1/client/niif18/modelos/modelos-2026/..%2f..%2fmanifiesto.json",
    ):
        r = client.get(ruta, **auth)
        assert r.status_code in (400, 403, 404), f"{ruta} devolvió {r.status_code}"


def test_operador_si_ve_y_descarga_los_modelos(client, db_session, biblioteca, admin_headers):
    """Un operador entra al portal con su mismo usuario y sí accede."""
    r = client.get("/api/v1/client/niif18/me", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["usuario"]["operador"] is True

    r = client.get("/api/v1/client/niif18/modelos", headers=admin_headers)
    assert r.status_code == 200
    assert len(r.json()["modelos"]) == 2

    r = client.get(
        "/api/v1/client/niif18/modelos/modelos-niif18/EY_GoodGroup.pdf",
        headers=admin_headers,
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/pdf")

    # Y su manifiesto sí lista los modelos
    r = client.get("/api/v1/client/niif18/normas", headers=admin_headers)
    assert r.status_code == 200
    assert len(r.json()["modelos"]) == 2


# ---------------------------------------------------------------- catálogo
def test_la_herramienta_esta_registrada_en_la_categoria_niif():
    from backend.app.client_portal.tool_registry import CATEGORIES, TOOLS

    assert TOOL in TOOLS
    t = TOOLS[TOOL]
    assert t.category == "NIIF"
    assert t.slots == {}
    assert t.processor is None
    assert t.enabled is True
    assert any(c["id"] == "NIIF" for c in CATEGORIES)


def test_sin_biblioteca_disponible_responde_503(client, db_session, monkeypatch, tmp_path):
    """Sin biblioteca, el módulo degrada a 503 en vez de romper la plataforma."""
    monkeypatch.setenv("NIIF18_BIBLIOTECA_DIR", str(tmp_path / "no-existe"))
    auth = _login_cliente(client, db_session)
    r = client.get("/api/v1/client/niif18/normas", **auth)
    assert r.status_code == 503


def test_la_ruta_por_defecto_es_la_que_deja_el_dockerfile():
    """El default del código y la ruta del Dockerfile.render deben coincidir.

    El Dockerfile copia la biblioteca a /app/base-normativa/libro y el módulo
    vive en /app/backend/app/client_portal/, así que `parents[3]` es /app. Si
    alguien mueve el módulo de carpeta, este test lo atrapa antes de que el
    despliegue quede silenciosamente sin normativa.
    """
    from backend.app.client_portal import niif18

    assert niif18.BIBLIOTECA_POR_DEFECTO.name == "libro"
    assert niif18.BIBLIOTECA_POR_DEFECTO.parent.name == "base-normativa"
    # La raíz calculada es la del proyecto: contiene el paquete `backend`.
    assert (niif18.RAIZ_PROYECTO / "backend" / "app").is_dir()

    dockerfile = (niif18.RAIZ_PROYECTO / "Dockerfile.render").read_text(encoding="utf-8")
    assert "/app/base-normativa/libro" in dockerfile
    assert "NIIF18_REPO_TOKEN" in dockerfile
