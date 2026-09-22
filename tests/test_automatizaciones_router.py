"""Tarea 6 del plan de Automatizaciones: endpoints del Command Center.

Supabase y el correo van simulados (igual que test_automatizaciones_service.py);
aquí se prueba el router: permisos, códigos HTTP y validación de payload.
"""

import datetime
import itertools
import uuid

import pytest

from backend.app.auth.jwt_tokens import create_access_token
from backend.app.auth.models import Role
from backend.app.auth.service import create_user
from backend.app.automatizaciones import service
from backend.app.context.models import Client, Organization
from backend.app.db.session import SessionLocal

OPERADOR = "op-router@auditconsulting.ec"
_ids = itertools.count(70000)


@pytest.fixture()
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


def _email(p):
    return f"{p}-{uuid.uuid4().hex[:8]}@example.com"


def _slug(p):
    return f"{p}-{uuid.uuid4().hex[:6]}"


@pytest.fixture()
def org_client(db):
    slug = _slug("aut")
    org = Organization(name=f"ACG-{slug}", slug=slug, is_active=True)
    db.add(org)
    db.commit()
    db.refresh(org)
    cli = Client(organization_id=org.id, name=f"Cliente {slug}", is_active=True)
    db.add(cli)
    db.commit()
    db.refresh(cli)
    return cli


@pytest.fixture()
def admin_token(db):
    u = create_user(db, email=_email("admin"), password="x", role=Role.admin)
    return create_access_token(subject=u.email, role="admin")


@pytest.fixture()
def staff_token(db):
    u = create_user(db, email=_email("staff"), password="x", role=Role.user)
    return create_access_token(subject=u.email, role="user")


@pytest.fixture()
def client_token(db):
    u = create_user(db, email=_email("cliente"), password="x", role=Role.client)
    return create_access_token(subject=u.email, role="client")


class FakeSupabase:
    def __init__(self, falla=None):
        self.llamadas = []
        self.falla = falla
        self.usuarios_vivos = set()

    def _quiza_fallar(self, nombre):
        if self.falla == nombre:
            from backend.app.automatizaciones.supabase_admin import SupabaseAdminError

            raise SupabaseAdminError(f"falla simulada en {nombre}: detalle-secreto-xyz")

    def crear_usuario(self, email, nombre):
        self.llamadas.append(("crear_usuario", email, nombre))
        self._quiza_fallar("crear_usuario")
        uid = f"uid-{email}"
        self.usuarios_vivos.add(uid)
        return {"id": uid, "email": email}

    def enlace_acceso(self, email, redirect_to):
        self.llamadas.append(("enlace_acceso", email, redirect_to))
        self._quiza_fallar("enlace_acceso")
        return f"https://supabase.local/verify?token=tok-{email}"

    def bloquear_usuario(self, user_id, bloquear):
        self.llamadas.append(("bloquear_usuario", user_id, bloquear))
        self._quiza_fallar("bloquear_usuario")

    def borrar_usuario(self, user_id):
        self.llamadas.append(("borrar_usuario", user_id))
        self._quiza_fallar("borrar_usuario")
        self.usuarios_vivos.discard(user_id)

    def consultar(self, tabla, params):
        self.llamadas.append(("consultar", tabla, params))
        self._quiza_fallar("consultar")
        return []


class FakeCorreo:
    def __init__(self, resultado={"id": "msg"}):  # noqa: B006
        self.enviados = []
        self.resultado = resultado

    def send_automatizacion_acceso(self, **kw):
        self.enviados.append(kw)
        return self.resultado


@pytest.fixture()
def sup(monkeypatch):
    fake = FakeSupabase()
    for nombre in ("crear_usuario", "enlace_acceso", "bloquear_usuario", "borrar_usuario", "consultar"):
        monkeypatch.setattr(service.sa, nombre, getattr(fake, nombre))
    return fake


@pytest.fixture()
def correo(monkeypatch):
    fake = FakeCorreo()
    monkeypatch.setattr(
        service.email_mod, "send_automatizacion_acceso", fake.send_automatizacion_acceso
    )
    return fake


def _payload(cid, **extra):
    datos = dict(
        client_id=cid,
        herramienta="PRESUPUESTOS_IA",
        empresa_nombre="Comercial Andina S.A.",
        admin_nombre="Ana Pérez",
        admin_email=_email("admin"),
    )
    datos.update(extra)
    return datos


def _alta(client, token, cid, **extra):
    return client.post(
        "/api/v1/staff/automatizaciones/cuentas",
        json=_payload(cid, **extra),
        headers={"Authorization": f"Bearer {token}"},
    )


BASE = "/api/v1/staff/automatizaciones"


# --- Auth --------------------------------------------------------------


def test_listar_sin_token_401(client):
    r = client.get(f"{BASE}/cuentas")
    assert r.status_code == 401


def test_listar_rol_client_no_autorizado(client, client_token):
    r = client.get(
        f"{BASE}/cuentas", headers={"Authorization": f"Bearer {client_token}"}
    )
    # get_current_user rechaza el rol client con 401 (defense-in-depth);
    # el resultado observable para el llamador es "no autorizado".
    assert r.status_code in (401, 403)


# --- Alta ----------------------------------------------------------------


def test_alta_y_listado_con_staff(client, staff_token, org_client, sup, correo):
    r = _alta(client, staff_token, org_client.id)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["client_id"] == org_client.id
    assert body["client_nombre"] == org_client.name
    assert body["herramienta"] == "PRESUPUESTOS_IA"
    assert body["empresa_nombre"] == "Comercial Andina S.A."
    assert body["admin_nombre"] == "Ana Pérez"
    assert body["estado"] == "activa"
    assert body["empresa_id_app"] is None

    rl = client.get(
        f"{BASE}/cuentas?client_id={org_client.id}",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert rl.status_code == 200
    filas = rl.json()
    assert len(filas) == 1
    assert filas[0]["id"] == body["id"]
    assert filas[0]["client_nombre"] == org_client.name


def test_alta_duplicada_409(client, staff_token, org_client, sup, correo):
    r1 = _alta(client, staff_token, org_client.id)
    assert r1.status_code == 201, r1.text
    r2 = _alta(client, staff_token, org_client.id, admin_email=_email("otro"))
    assert r2.status_code == 409, r2.text


def test_herramienta_invalida_422(client, staff_token, org_client):
    r = _alta(client, staff_token, org_client.id, herramienta="NO_EXISTE")
    assert r.status_code == 422, r.text


def test_herramienta_deshabilitada_fuera_de_categoria_422(client, staff_token, org_client):
    """PLANIFICACION_IA está deshabilitada, pero lo que valida el schema es
    la categoría; una herramienta de otra categoría (p. ej. TRIBUTARIAS)
    tampoco debe aceptarse aquí."""
    r = _alta(client, staff_token, org_client.id, herramienta="ICT_2025")
    assert r.status_code == 422, r.text


def test_vigencia_pasada_422(client, staff_token, org_client):
    ayer = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    r = _alta(client, staff_token, org_client.id, vigencia_hasta=ayer)
    assert r.status_code == 422, r.text


def test_vigencia_futura_ok(client, staff_token, org_client, sup, correo):
    manana = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
    r = _alta(client, staff_token, org_client.id, vigencia_hasta=manana)
    assert r.status_code == 201, r.text
    assert r.json()["vigencia_hasta"] == manana


def test_nombres_vacios_422(client, staff_token, org_client):
    r = _alta(client, staff_token, org_client.id, empresa_nombre="   ")
    assert r.status_code == 422, r.text


def test_correo_invalido_422(client, staff_token, org_client):
    r = _alta(client, staff_token, org_client.id, admin_email="no-es-correo")
    assert r.status_code == 422, r.text


# --- Ciclo de vida ---------------------------------------------------------


def test_reenviar_acceso(client, staff_token, org_client, sup, correo):
    r = _alta(client, staff_token, org_client.id)
    cuenta_id = r.json()["id"]
    correo.enviados.clear()
    rr = client.post(
        f"{BASE}/cuentas/{cuenta_id}/reenviar-acceso",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert rr.status_code == 200, rr.text
    assert len(correo.enviados) == 1


def test_suspender_y_reactivar(client, staff_token, org_client, sup, correo):
    r = _alta(client, staff_token, org_client.id)
    cuenta_id = r.json()["id"]
    h = {"Authorization": f"Bearer {staff_token}"}

    rs = client.post(f"{BASE}/cuentas/{cuenta_id}/suspender", headers=h)
    assert rs.status_code == 200, rs.text
    assert rs.json()["estado"] == "suspendida"

    rr = client.post(f"{BASE}/cuentas/{cuenta_id}/reactivar", headers=h)
    assert rr.status_code == 200, rr.text
    assert rr.json()["estado"] == "activa"


def test_refrescar_empresa(client, staff_token, org_client, sup, correo):
    r = _alta(client, staff_token, org_client.id)
    cuenta_id = r.json()["id"]
    rr = client.post(
        f"{BASE}/cuentas/{cuenta_id}/refrescar-empresa",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert rr.status_code == 200, rr.text
    assert rr.json()["empresa_id_app"] is None  # sup.consultar no devuelve nada


# --- Borrado: solo admin, con confirmación ----------------------------------


def test_borrar_rol_user_403(client, staff_token, org_client, sup, correo):
    r = _alta(client, staff_token, org_client.id)
    cuenta_id = r.json()["id"]
    rd = client.delete(
        f"{BASE}/cuentas/{cuenta_id}?confirmado=true",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert rd.status_code == 403


def test_borrar_admin_sin_confirmado_400(client, admin_token, staff_token, org_client, sup, correo):
    r = _alta(client, staff_token, org_client.id)
    cuenta_id = r.json()["id"]
    rd = client.delete(
        f"{BASE}/cuentas/{cuenta_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert rd.status_code == 400


def test_borrar_admin_confirmado_200(client, admin_token, staff_token, org_client, sup, correo):
    r = _alta(client, staff_token, org_client.id)
    cuenta_id = r.json()["id"]
    rd = client.delete(
        f"{BASE}/cuentas/{cuenta_id}?confirmado=true",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert rd.status_code == 200, rd.text

    rl = client.get(
        f"{BASE}/cuentas?client_id={org_client.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert rl.json() == []


# --- SupabaseAdminError -> 502 sin cuerpo crudo -----------------------------


def test_alta_con_fallo_supabase_502_sin_texto_crudo(client, staff_token, org_client, monkeypatch):
    fake = FakeSupabase(falla="enlace_acceso")
    for nombre in ("crear_usuario", "enlace_acceso", "bloquear_usuario", "borrar_usuario", "consultar"):
        monkeypatch.setattr(service.sa, nombre, getattr(fake, nombre))
    fake_correo = FakeCorreo()
    monkeypatch.setattr(
        service.email_mod, "send_automatizacion_acceso", fake_correo.send_automatizacion_acceso
    )

    r = _alta(client, staff_token, org_client.id)
    assert r.status_code == 502, r.text
    cuerpo = r.text
    assert "detalle-secreto-xyz" not in cuerpo
    assert "falla simulada" not in cuerpo


def test_suspender_con_fallo_supabase_502(client, staff_token, org_client, sup, correo, monkeypatch):
    r = _alta(client, staff_token, org_client.id)
    cuenta_id = r.json()["id"]
    sup.falla = "bloquear_usuario"
    rs = client.post(
        f"{BASE}/cuentas/{cuenta_id}/suspender",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert rs.status_code == 502, rs.text
    assert "detalle-secreto-xyz" not in rs.text


# --- Listado muestra vigencia vencida como suspendida -----------------------


def test_listado_muestra_suspendida_si_vencida(client, staff_token, org_client, sup, correo):
    ayer = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    # vigencia pasada se rechaza en el alta; se crea vigente y se edita
    # directamente en la fila para simular el paso del tiempo.
    r = _alta(client, staff_token, org_client.id)
    cuenta_id = r.json()["id"]

    from backend.app.automatizaciones.models import AutCuenta

    db = SessionLocal()
    try:
        cuenta = db.get(AutCuenta, cuenta_id)
        cuenta.vigencia_hasta = datetime.date.today() - datetime.timedelta(days=1)
        db.commit()
    finally:
        db.close()

    rl = client.get(
        f"{BASE}/cuentas?client_id={org_client.id}",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    fila = rl.json()[0]
    assert fila["estado"] == "suspendida"
    assert fila["vencida"] is True
