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


def test_la_ruta_por_defecto_coincide_con_el_punto_de_montaje():
    """El default del código es donde se monta el volumen de la biblioteca.

    La biblioteca se monta como volumen persistente en /app/base-normativa, y
    el módulo vive en /app/backend/app/client_portal/, así que `parents[3]` es
    /app. Si alguien mueve el módulo de carpeta, este test lo atrapa antes de
    que el despliegue quede silenciosamente sin normativa.
    """
    from backend.app.client_portal import niif18

    assert niif18.BIBLIOTECA_POR_DEFECTO.name == "libro"
    assert niif18.BIBLIOTECA_POR_DEFECTO.parent.name == "base-normativa"
    # La raíz calculada es la del proyecto: contiene el paquete `backend`.
    assert (niif18.RAIZ_PROYECTO / "backend" / "app").is_dir()


def test_el_build_no_lleva_ninguna_credencial():
    """Guardián de la decisión: la imagen NO se construye con credenciales.

    La biblioteca llega por volumen, no descargándose en el build. Traerla
    durante el build exigía un token de GitHub que, en Coolify, solo puede
    viajar como build arg y queda registrado en `docker history`. Si alguien
    reintroduce esa descarga, este test lo detiene: no es un detalle de estilo,
    es la diferencia entre tener o no una credencial filtrable en la imagen.
    """
    from backend.app.client_portal import niif18

    dockerfile = (niif18.RAIZ_PROYECTO / "Dockerfile.render").read_text(encoding="utf-8")
    prohibido = ("NIIF18_REPO_TOKEN", "--mount=type=secret", "/run/secrets/niif18_token")
    presentes = [x for x in prohibido if x in dockerfile]
    assert not presentes, (
        "El Dockerfile volvió a llevar credenciales de build: "
        + ", ".join(presentes)
        + ". La biblioteca debe montarse como volumen (ver docs/DEPLOYMENT.md)."
    )
    # Y la ruta de montaje sigue documentada en el propio Dockerfile.
    assert "/app/base-normativa" in dockerfile


# ------------------------------------------------- pase de biblioteca (cookie)
# El bug: cada norma es un <a href> a /biblioteca/... Al hacer clic el navegador
# NAVEGA, y una navegación no puede llevar la cabecera Authorization, así que
# todas las normas respondían 401. El pase es una cookie HttpOnly de vida corta
# que el navegador sí manda en esa navegación.
@pytest.fixture()
def pase_sin_https(monkeypatch):
    """El TestClient habla http; sin esto la cookie Secure no se enviaría."""
    monkeypatch.setenv("NIIF18_PASE_COOKIE_SECURE", "false")


def _abrir_pase(client, sesion):
    r = client.post(
        "/api/v1/client/niif18/pase", headers=sesion["headers"], cookies=sesion["cookies"]
    )
    assert r.status_code == 200, r.text
    return r


def test_abrir_una_norma_navegando_sin_pase_da_401(client, db_session, biblioteca):
    """Regresión del bug: el enlace de una norma no lleva Authorization."""
    r = client.get("/api/v1/client/niif18/biblioteca/normas/ifrs18.html")
    assert r.status_code == 401
    assert "pase" in r.json()["detail"].lower()


def test_con_el_pase_la_norma_abre_al_navegar(client, db_session, biblioteca, pase_sin_https):
    sesion = _login_cliente(client, db_session)
    _abrir_pase(client, sesion)
    # Navegación pura: ni cabecera Authorization ni cookies de sesión.
    r = client.get("/api/v1/client/niif18/biblioteca/normas/ifrs18.html")
    assert r.status_code == 200, r.text
    assert "NIIF 18" in r.text


def test_la_cookie_del_pase_es_httponly_y_de_ruta_restringida(
    client, db_session, biblioteca, pase_sin_https
):
    sesion = _login_cliente(client, db_session)
    r = _abrir_pase(client, sesion)
    cabecera = r.headers["set-cookie"]
    assert "httponly" in cabecera.lower()
    assert "path=/api/v1/client/niif18" in cabecera.lower()
    assert "samesite=lax" in cabecera.lower()


def test_el_pase_no_abre_ningun_otro_endpoint_del_portal(
    client, db_session, biblioteca, pase_sin_https
):
    """El pase no lleva rol ni sid: no es un token de sesión."""
    sesion = _login_cliente(client, db_session)
    _abrir_pase(client, sesion)
    pase = client.cookies.get("niif18_pase")
    assert pase
    # Ni siquiera presentándolo como Bearer en el catálogo del propio módulo.
    for ruta in ("/api/v1/client/niif18/normas", "/api/v1/client/niif18/me"):
        r = client.get(ruta, headers={"Authorization": f"Bearer {pase}"})
        assert r.status_code in (401, 403), f"{ruta} -> {r.status_code}"
    client.cookies.clear()


def test_el_cliente_con_pase_sigue_sin_alcanzar_los_modelos(
    client, db_session, biblioteca, pase_sin_https
):
    """El pase no relaja el control de rol de los modelos de las firmas."""
    sesion = _login_cliente(client, db_session)
    _abrir_pase(client, sesion)
    r = client.get("/api/v1/client/niif18/modelos/modelos-niif18/EY_GoodGroup.pdf")
    assert r.status_code == 403
    client.cookies.clear()


def test_el_operador_con_pase_si_descarga_el_modelo(
    client, db_session, biblioteca, pase_sin_https, admin_headers
):
    r = client.post("/api/v1/client/niif18/pase", headers=admin_headers)
    assert r.status_code == 200, r.text
    r = client.get("/api/v1/client/niif18/modelos/modelos-niif18/EY_GoodGroup.pdf")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    client.cookies.clear()


def test_el_pase_caducado_lo_dice_claro(client, db_session, biblioteca, pase_sin_https, monkeypatch):
    import datetime

    import jwt as _jwt

    from backend.app.auth.jwt_tokens import _secret
    from backend.app.client_portal import niif18 as mod

    ayer = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) - datetime.timedelta(days=1)
    vencido = _jwt.encode(
        {"sub": "quien@example.com", "scope": mod.PASE_SCOPE, "iat": ayer, "exp": ayer},
        _secret(),
        algorithm="HS256",
    )
    client.cookies.set("niif18_pase", vencido, path="/api/v1/client/niif18")
    r = client.get("/api/v1/client/niif18/biblioteca/normas/ifrs18.html")
    assert r.status_code == 401
    assert "expiró" in r.json()["detail"]
    client.cookies.clear()


def test_el_pase_se_cierra(client, db_session, biblioteca, pase_sin_https):
    sesion = _login_cliente(client, db_session)
    _abrir_pase(client, sesion)
    assert client.get("/api/v1/client/niif18/biblioteca/normas/ifrs18.html").status_code == 200
    r = client.delete("/api/v1/client/niif18/pase")
    assert r.status_code == 200
    assert client.get("/api/v1/client/niif18/biblioteca/normas/ifrs18.html").status_code == 401
    client.cookies.clear()


def test_la_cookie_del_pase_es_segura_por_defecto(client, db_session, biblioteca, monkeypatch):
    """Sin la variable de desarrollo, la cookie NUNCA viaja por http."""
    monkeypatch.delenv("NIIF18_PASE_COOKIE_SECURE", raising=False)
    sesion = _login_cliente(client, db_session)
    r = client.post(
        "/api/v1/client/niif18/pase", headers=sesion["headers"], cookies=sesion["cookies"]
    )
    assert r.status_code == 200
    assert "secure" in r.headers["set-cookie"].lower()
    client.cookies.clear()


def test_el_pase_de_un_operador_no_autentica_endpoints_de_staff(client, db_session, biblioteca):
    """El pase NO es un token de sesión, ni para un operador.

    Regresión de una escalada real encontrada en revisión: firmado con el
    secreto común de la plataforma, el pase de un admin abría
    `GET /api/v1/staff/tools` con 200, porque `auth.deps._user_from_token`
    comprueba el rol del usuario en la base y no el claim `role` (que el pase
    no lleva). Se firma con una clave DERIVADA para que no verifique nunca
    contra el secreto de la plataforma.
    """
    from backend.app.auth.service import create_user
    from backend.app.client_portal import niif18 as mod

    email = f"op-pase-{uuid.uuid4().hex[:8]}@example.com"
    create_user(db_session, email=email, password="Clave-Muy-Larga-123", role=Role.admin)
    operador = get_user_by_email(db_session, email)
    pase = mod._emitir_pase(operador)

    r = client.get("/api/v1/staff/tools", headers={"Authorization": f"Bearer {pase}"})
    assert r.status_code in (401, 403), (
        f"el pase abrió un endpoint de staff ({r.status_code})"
    )
    # Y tampoco vale como token del portal.
    r = client.get("/api/v1/client/niif18/normas", headers={"Authorization": f"Bearer {pase}"})
    assert r.status_code in (401, 403)


def test_el_pase_no_sobrevive_al_cierre_de_sesion_del_cliente(
    client, db_session, biblioteca, pase_sin_https, monkeypatch
):
    """Sesión única: al salir del portal, el pase deja de abrir la biblioteca."""
    monkeypatch.setenv("CLIENT_PORTAL_SESSION_CHECK_ENABLED", "true")
    sesion = _login_cliente(client, db_session)
    _abrir_pase(client, sesion)
    assert client.get("/api/v1/client/niif18/biblioteca/normas/ifrs18.html").status_code == 200

    r = client.post("/api/v1/client/auth/logout", headers=sesion["headers"], cookies=sesion["cookies"])
    assert r.status_code in (200, 204), r.text

    r = client.get("/api/v1/client/niif18/biblioteca/normas/ifrs18.html")
    assert r.status_code == 401, f"el pase siguió abriendo tras el logout ({r.status_code})"
    assert "sesión" in r.json()["detail"].lower()
    client.cookies.clear()
