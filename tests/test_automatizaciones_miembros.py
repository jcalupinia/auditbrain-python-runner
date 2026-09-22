"""Tarea 9 del plan de Automatizaciones: el ADMINISTRADOR de la empresa
cliente da de alta y restablece el acceso de SU personal en la app de
presupuestos, pasando por el portal (el navegador nunca tiene la llave de
servicio).

No hay staff/JWT del Command Center aquí: quien llama es el propio
administrador ya logueado en la app, con su ``access_token`` de Supabase.
Supabase y el correo van simulados (mismo patrón que
``test_automatizaciones_router.py``); aquí se prueba el router: autenticación
por token de la app, 403/404 delegados a las reglas de la base, reversa de
cuentas nuevas si falla el correo, 502 genérico y que ni el token ni el
enlace se filtren en los logs.
"""

import logging
import uuid

import pytest

from backend.app.automatizaciones import router_miembros
from backend.app.automatizaciones.supabase_admin import SupabaseAdminError

BASE = "/api/v1/app/miembros"
TOKEN = "token-del-admin-empresa"


class FakeSupabase:
    def __init__(self, falla=None, es_admin=True, miembros=None, usuario_existente=False):
        self.llamadas = []
        self.falla = falla
        self.es_admin = es_admin
        self.miembros = miembros if miembros is not None else []
        self.usuario_existente = usuario_existente
        self.usuarios_vivos = set()
        self.borrados = []
        self._ultimo_miembro = None

    def _quiza_fallar(self, nombre):
        if self.falla == nombre:
            raise SupabaseAdminError(f"falla simulada en {nombre}: detalle-secreto-xyz")

    def usuario_de_token(self, token):
        self.llamadas.append(("usuario_de_token", token))
        self._quiza_fallar("usuario_de_token")
        if token != TOKEN:
            raise SupabaseAdminError("401 invalid token: detalle-secreto-xyz")
        return {"id": "uid-admin", "email": "admin@empresa.ec"}

    def rpc(self, nombre, payload, *, token_usuario=None):
        self.llamadas.append(("rpc", nombre, payload, token_usuario))
        self._quiza_fallar(f"rpc:{nombre}")
        if nombre == "agregar_miembro":
            if not self.es_admin:
                raise SupabaseAdminError(
                    "Supabase 400 en POST /rest/v1/rpc/agregar_miembro: "
                    '{"message":"Solo el administrador de la empresa puede '
                    'gestionar miembros"}'
                )
            self._ultimo_miembro = {
                "id": "miembro-uuid-1",
                "empresa_id": payload["_empresa_id"],
                "email": payload["_email"],
                "nombre": payload["_nombre"],
                "role": payload["_role"],
                "departamento_id": payload["_departamento_id"],
                "estado": "pendiente",
            }
            return self._ultimo_miembro["id"]
        if nombre == "es_admin_empresa":
            return self.es_admin
        raise AssertionError(f"rpc inesperado: {nombre}")

    def crear_usuario(self, email, nombre):
        self.llamadas.append(("crear_usuario", email, nombre))
        self._quiza_fallar("crear_usuario")
        if self.usuario_existente:
            raise SupabaseAdminError(
                "422: A user with this email address has already been "
                "registered"
            )
        uid = f"uid-{email}"
        self.usuarios_vivos.add(uid)
        return {"id": uid, "email": email}

    def enlace_acceso(self, email, redirect_to):
        self.llamadas.append(("enlace_acceso", email, redirect_to))
        self._quiza_fallar("enlace_acceso")
        return f"https://supabase.local/verify?token=tok-{email}"

    def borrar_usuario(self, user_id):
        self.llamadas.append(("borrar_usuario", user_id))
        self.borrados.append(user_id)
        self.usuarios_vivos.discard(user_id)

    def consultar(self, tabla, params, *, token_usuario=None):
        self.llamadas.append(("consultar", tabla, params, token_usuario))
        self._quiza_fallar("consultar")
        if tabla == "empresas":
            return [{"nombre": "Comercial Andina S.A."}]
        if tabla == "empresa_miembros":
            if self.miembros:
                return list(self.miembros)
            if self._ultimo_miembro:
                return [dict(self._ultimo_miembro, estado="activo")]
            return []
        return []


class FakeCorreo:
    def __init__(self, resultado={"id": "msg"}):  # noqa: B006
        self.enviados = []
        self.resultado = resultado

    def send_automatizacion_acceso(self, **kw):
        self.enviados.append(kw)
        return self.resultado


def _parchar_supabase(monkeypatch, fake):
    for nombre in (
        "usuario_de_token",
        "rpc",
        "crear_usuario",
        "enlace_acceso",
        "borrar_usuario",
        "consultar",
    ):
        monkeypatch.setattr(router_miembros.sa, nombre, getattr(fake, nombre))
    return fake


@pytest.fixture()
def sup(monkeypatch):
    return _parchar_supabase(monkeypatch, FakeSupabase())


@pytest.fixture()
def correo(monkeypatch):
    fake = FakeCorreo()
    monkeypatch.setattr(
        router_miembros.email_mod, "send_automatizacion_acceso", fake.send_automatizacion_acceso
    )
    return fake


def _headers(token=TOKEN):
    return {"Authorization": f"Bearer {token}"}


def _payload(**extra):
    datos = dict(
        empresa_id=str(uuid.uuid4()),
        email=f"{uuid.uuid4().hex[:8]}@example.com",
        nombre="Ana Pérez",
        role="consulta",
    )
    datos.update(extra)
    return datos


# --- Auth --------------------------------------------------------------


def test_alta_sin_token_401(client):
    r = client.post(BASE, json=_payload())
    assert r.status_code == 401


def test_alta_token_invalido_401(client, sup, correo):
    r = client.post(BASE, json=_payload(), headers=_headers("token-que-no-es"))
    assert r.status_code == 401
    assert not any(l[0] == "rpc" for l in sup.llamadas)


def test_reenviar_sin_token_401(client):
    r = client.post(f"{BASE}/reenviar-acceso", json={"empresa_id": str(uuid.uuid4()), "email": "a@x.ec"})
    assert r.status_code == 401


# --- Alta ----------------------------------------------------------------


def test_alta_correcta_201(client, sup, correo):
    payload = _payload()
    r = client.post(BASE, json=payload, headers=_headers())
    assert r.status_code == 201, r.text

    llamadas_rpc = [l for l in sup.llamadas if l[0] == "rpc" and l[1] == "agregar_miembro"]
    assert len(llamadas_rpc) == 1
    assert llamadas_rpc[0][3] == TOKEN  # se llamó CON el token del usuario

    assert any(l[0] == "crear_usuario" for l in sup.llamadas)
    assert len(correo.enviados) == 1

    body = r.json()
    assert body["email"] == payload["email"]
    assert body["role"] == "consulta"


def test_alta_rol_invalido_422(client, sup, correo):
    r = client.post(BASE, json=_payload(role="dueño-del-mundo"), headers=_headers())
    assert r.status_code == 422, r.text


def test_alta_correo_invalido_422(client, sup, correo):
    r = client.post(BASE, json=_payload(email="no-es-correo"), headers=_headers())
    assert r.status_code == 422, r.text


def test_alta_no_administrador_403_sin_crear_cuenta_ni_correo(client, correo, monkeypatch):
    fake = _parchar_supabase(monkeypatch, FakeSupabase(es_admin=False))
    r = client.post(BASE, json=_payload(), headers=_headers())
    assert r.status_code == 403, r.text
    assert not any(l[0] == "crear_usuario" for l in fake.llamadas)
    assert correo.enviados == []


def test_alta_correo_ya_tiene_cuenta_no_duplica_pero_envia_enlace(client, correo, monkeypatch):
    fake = _parchar_supabase(monkeypatch, FakeSupabase(usuario_existente=True))
    r = client.post(BASE, json=_payload(), headers=_headers())
    assert r.status_code == 201, r.text
    assert fake.usuarios_vivos == set()  # no se creó cuenta nueva
    assert len(correo.enviados) == 1


def test_fallo_correo_tras_cuenta_nueva_la_borra(client, monkeypatch):
    fake = _parchar_supabase(monkeypatch, FakeSupabase(falla="enlace_acceso"))
    fake_correo = FakeCorreo()
    monkeypatch.setattr(
        router_miembros.email_mod, "send_automatizacion_acceso", fake_correo.send_automatizacion_acceso
    )
    r = client.post(BASE, json=_payload(), headers=_headers())
    assert r.status_code == 502, r.text
    assert len(fake.borrados) == 1
    assert fake.usuarios_vivos == set()
    assert fake_correo.enviados == []


def test_fallo_correo_tras_cuenta_existente_no_borra_nada(client, monkeypatch):
    fake = _parchar_supabase(
        monkeypatch, FakeSupabase(falla="enlace_acceso", usuario_existente=True)
    )
    fake_correo = FakeCorreo()
    monkeypatch.setattr(
        router_miembros.email_mod, "send_automatizacion_acceso", fake_correo.send_automatizacion_acceso
    )
    r = client.post(BASE, json=_payload(), headers=_headers())
    assert r.status_code == 502, r.text
    assert fake.borrados == []


# --- Reenviar acceso ---------------------------------------------------


def test_reenviar_acceso_no_admin_403(client, correo, monkeypatch):
    _parchar_supabase(monkeypatch, FakeSupabase(es_admin=False))
    r = client.post(
        f"{BASE}/reenviar-acceso",
        json={"empresa_id": str(uuid.uuid4()), "email": "a@x.ec"},
        headers=_headers(),
    )
    assert r.status_code == 403, r.text
    assert correo.enviados == []


def test_reenviar_acceso_no_miembro_404(client, correo, monkeypatch):
    _parchar_supabase(monkeypatch, FakeSupabase(es_admin=True, miembros=[]))
    r = client.post(
        f"{BASE}/reenviar-acceso",
        json={"empresa_id": str(uuid.uuid4()), "email": "no-es-miembro@x.ec"},
        headers=_headers(),
    )
    assert r.status_code == 404, r.text
    assert correo.enviados == []


def test_reenviar_acceso_correcto_200(client, correo, monkeypatch):
    _parchar_supabase(
        monkeypatch, FakeSupabase(es_admin=True, miembros=[{"id": "m1"}])
    )
    r = client.post(
        f"{BASE}/reenviar-acceso",
        json={"empresa_id": str(uuid.uuid4()), "email": "si-es-miembro@x.ec"},
        headers=_headers(),
    )
    assert r.status_code == 200, r.text
    assert len(correo.enviados) == 1


# --- SupabaseAdminError -> 502 sin cuerpo crudo -----------------------------


def test_alta_fallo_supabase_502_sin_texto_crudo(client, correo, monkeypatch):
    fake = _parchar_supabase(monkeypatch, FakeSupabase(falla="rpc:agregar_miembro"))
    r = client.post(BASE, json=_payload(), headers=_headers())
    assert r.status_code == 502, r.text
    assert "detalle-secreto-xyz" not in r.text


def test_reenviar_acceso_fallo_supabase_502_sin_texto_crudo(client, correo, monkeypatch):
    _parchar_supabase(monkeypatch, FakeSupabase(falla="rpc:es_admin_empresa"))
    r = client.post(
        f"{BASE}/reenviar-acceso",
        json={"empresa_id": str(uuid.uuid4()), "email": "a@x.ec"},
        headers=_headers(),
    )
    assert r.status_code == 502, r.text
    assert "detalle-secreto-xyz" not in r.text


# --- Nunca se filtran el token ni el enlace ---------------------------------


def test_token_y_enlace_no_aparecen_en_logs(client, sup, correo, caplog):
    caplog.set_level(logging.INFO, logger=router_miembros.log.name)
    r = client.post(BASE, json=_payload(), headers=_headers())
    assert r.status_code == 201, r.text
    texto = "\n".join(rec.getMessage() for rec in caplog.records)
    assert TOKEN not in texto
    assert "supabase.local/verify" not in texto
