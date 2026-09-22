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
    def __init__(self, falla=None, empresas=None):
        self.llamadas = []
        self.falla = falla
        self.empresas = empresas if empresas is not None else []
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
        if tabla == "empresas":
            return list(self.empresas)
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


def test_vigencia_usa_la_fecha_de_ecuador_no_la_utc_del_servidor(monkeypatch):
    """[FIX revisión final] a las 02:00 UTC todavía es 31-dic en Ecuador
    (UTC-5); una vigencia hasta esa fecha NO debe rechazarse como pasada."""
    from backend.app.automatizaciones import schemas, service

    class _DatetimeFijo(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            momento_utc = datetime.datetime(2026, 1, 1, 2, 0, tzinfo=datetime.timezone.utc)
            return momento_utc.astimezone(tz) if tz else momento_utc

    monkeypatch.setattr(service.datetime, "datetime", _DatetimeFijo)

    schemas.CuentaCreate(
        client_id=1,
        herramienta="PRESUPUESTOS_IA",
        empresa_nombre="X",
        admin_nombre="Y",
        admin_email="a@x.ec",
        vigencia_hasta=datetime.date(2025, 12, 31),
    )


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


def test_borrar_admin_409_si_la_cuenta_ya_creo_una_empresa(
    client, admin_token, staff_token, org_client, sup, correo
):
    """CRÍTICO (revisión final): borrar el usuario borraría en cascada la
    empresa que ya creó en la app. El router debe traducirlo a 409, no dejar
    borrar."""
    r = _alta(client, staff_token, org_client.id)
    cuenta_id = r.json()["id"]
    sup.empresas = [{"nombre": "Comercial Andina S.A."}]

    rd = client.delete(
        f"{BASE}/cuentas/{cuenta_id}?confirmado=true",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert rd.status_code == 409, rd.text
    assert "Comercial Andina S.A." in rd.json()["detail"]
    assert "Suspender" in rd.json()["detail"]

    rl = client.get(
        f"{BASE}/cuentas?client_id={org_client.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert len(rl.json()) == 1  # sigue ahí


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


def test_listado_expone_estado_guardado_y_vencida_por_separado(
    client, staff_token, org_client, sup, correo
):
    """[FIX revisión final] el listado ya no colapsa el ``estado`` de una
    cuenta vencida a "suspendida": el frontend necesita el dato guardado
    (para decidir Suspender/Reactivar) y ``vencida`` aparte (para la
    etiqueta)."""
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
    assert fila["estado"] == "activa"  # el dato guardado, no el efectivo
    assert fila["vencida"] is True


# --- Correo ya registrado en GoTrue -> 409, no 502 --------------------------


def test_alta_correo_ya_registrado_en_gotrue_409(client, staff_token, org_client, monkeypatch):
    """[FIX revisión final] un 422 "already registered" de GoTrue es un error
    del cliente (409), no un fallo de infraestructura (502)."""
    from backend.app.automatizaciones.supabase_admin import SupabaseAdminError

    fake = FakeSupabase()

    def crear_usuario_ya_registrado(email, nombre):
        fake.llamadas.append(("crear_usuario", email, nombre))
        raise SupabaseAdminError(
            "422: A user with this email address has already been registered",
            status=422,
        )

    monkeypatch.setattr(service.sa, "crear_usuario", crear_usuario_ya_registrado)
    for nombre in ("enlace_acceso", "bloquear_usuario", "borrar_usuario", "consultar"):
        monkeypatch.setattr(service.sa, nombre, getattr(fake, nombre))
    fake_correo = FakeCorreo()
    monkeypatch.setattr(
        service.email_mod, "send_automatizacion_acceso", fake_correo.send_automatizacion_acceso
    )

    r = _alta(client, staff_token, org_client.id)
    assert r.status_code == 409, r.text
    assert "Presupuestos IA" in r.json()["detail"]
    assert fake_correo.enviados == []


def test_alta_correo_duplicado_email_exists_409(client, staff_token, org_client, monkeypatch):
    """Misma regla con el otro texto que usa GoTrue para el mismo caso."""
    from backend.app.automatizaciones.supabase_admin import SupabaseAdminError

    fake = FakeSupabase()

    def crear_usuario_ya_registrado(email, nombre):
        raise SupabaseAdminError('{"error_code":"email_exists"}', status=422)

    monkeypatch.setattr(service.sa, "crear_usuario", crear_usuario_ya_registrado)
    for nombre in ("enlace_acceso", "bloquear_usuario", "borrar_usuario", "consultar"):
        monkeypatch.setattr(service.sa, nombre, getattr(fake, nombre))

    r = _alta(client, staff_token, org_client.id)
    assert r.status_code == 409, r.text


def test_alta_fallo_5xx_de_supabase_sigue_siendo_502(client, staff_token, org_client, monkeypatch):
    """Un 5xx/red genuino sigue siendo 502: solo el 4xx "ya existe" cambia."""
    from backend.app.automatizaciones.supabase_admin import SupabaseAdminError

    fake = FakeSupabase()

    def crear_usuario_5xx(email, nombre):
        raise SupabaseAdminError("Supabase 503: upstream caído")  # status=None

    monkeypatch.setattr(service.sa, "crear_usuario", crear_usuario_5xx)
    for nombre in ("enlace_acceso", "bloquear_usuario", "borrar_usuario", "consultar"):
        monkeypatch.setattr(service.sa, nombre, getattr(fake, nombre))

    r = _alta(client, staff_token, org_client.id)
    assert r.status_code == 502, r.text


# --- Alta concurrente: IntegrityError -> 409 --------------------------------


def test_alta_concurrente_integrity_error_da_409(
    client, staff_token, org_client, sup, correo, monkeypatch
):
    """Dos altas concurrentes pueden pasar ambas el chequeo de duplicado
    (ninguna ve todavía el commit de la otra) y chocar recién en el INSERT
    real (constraint ``uq_aut_cuenta_cliente_herramienta``). El router debe
    traducir ese ``IntegrityError`` a 409, no tumbarse con un 500."""
    from sqlalchemy.exc import IntegrityError

    def crear_que_choca(*a, **kw):
        raise IntegrityError("INSERT", {}, Exception("uq_aut_cuenta_cliente_herramienta"))

    monkeypatch.setattr(service, "crear", crear_que_choca)

    r = _alta(client, staff_token, org_client.id)
    assert r.status_code == 409, r.text
    assert not any(c[0] == "crear_usuario" for c in sup.llamadas)
