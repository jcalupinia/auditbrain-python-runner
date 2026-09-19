"""Tarea 4 del plan de Automatizaciones: reglas del alta y del ciclo de vida.

El Supabase de la app y el correo van simulados: aquí se prueban las reglas,
no el transporte (eso es ``test_automatizaciones_supabase.py``).
"""

import datetime
import itertools
import logging

import pytest

from backend.app.automatizaciones import service
from backend.app.automatizaciones.models import AutCuenta
from backend.app.automatizaciones.supabase_admin import SupabaseAdminError
from backend.app.db.session import SessionLocal

OPERADOR = "op@auditconsulting.ec"
_ids = itertools.count(9000)


@pytest.fixture()
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


@pytest.fixture()
def cid():
    """client_id propio de cada test: la unicidad es (client_id, herramienta)."""
    return next(_ids)


class FakeSupabase:
    """Registra las llamadas y permite hacer fallar una en concreto."""

    def __init__(self, falla=None, miembros=None):
        self.llamadas = []
        self.falla = falla
        self.miembros = miembros if miembros is not None else []
        self.usuarios_vivos = set()

    def _quiza_fallar(self, nombre):
        if self.falla == nombre:
            raise SupabaseAdminError(f"falla simulada en {nombre}")

    def crear_usuario(self, email, nombre):
        self.llamadas.append(("crear_usuario", email, nombre))
        self._quiza_fallar("crear_usuario")
        uid = f"uid-{email}"
        self.usuarios_vivos.add(uid)
        return {"id": uid, "email": email}

    def enlace_acceso(self, email, redirect_to):
        self.llamadas.append(("enlace_acceso", email, redirect_to))
        self._quiza_fallar("enlace_acceso")
        return f"https://supabase.local/verify?token=tok-{email}&redirect_to={redirect_to}"

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
        return list(self.miembros)


class FakeCorreo:
    def __init__(self, resultado={"id": "msg"}):  # noqa: B006
        # ``None`` es un valor legítimo: es lo que devuelve send_email al fallar.
        self.enviados = []
        self.resultado = resultado

    def send_automatizacion_acceso(self, **kw):
        self.enviados.append(kw)
        return self.resultado


@pytest.fixture()
def sup(monkeypatch):
    fake = FakeSupabase()
    for nombre in (
        "crear_usuario",
        "enlace_acceso",
        "bloquear_usuario",
        "borrar_usuario",
        "consultar",
    ):
        monkeypatch.setattr(service.sa, nombre, getattr(fake, nombre))
    return fake


@pytest.fixture()
def correo(monkeypatch):
    fake = FakeCorreo()
    monkeypatch.setattr(
        service.email_mod, "send_automatizacion_acceso", fake.send_automatizacion_acceso
    )
    return fake


def _alta(db, cid, **extra):
    datos = dict(
        client_id=cid,
        herramienta="PRESUPUESTOS_IA",
        empresa_nombre="Comercial Andina S.A.",
        admin_email="Admin@Cliente.EC",
        admin_nombre="Ana Pérez",
        creado_por=OPERADOR,
    )
    datos.update(extra)
    return service.crear(db, **datos)


# --- Regla 1 y 2: alta atómica + correo -------------------------------------


def test_alta_crea_usuario_guarda_fila_y_envia_correo(db, cid, sup, correo):
    cuenta = _alta(db, cid)

    assert cuenta.id is not None
    assert cuenta.admin_email == "admin@cliente.ec"  # normalizado
    assert cuenta.admin_user_id_app == "uid-admin@cliente.ec"
    assert cuenta.estado == "activa"
    assert db.get(AutCuenta, cuenta.id) is not None

    tipos = [c[0] for c in sup.llamadas]
    assert tipos == ["crear_usuario", "enlace_acceso"]
    # El enlace vuelve a la pantalla de contraseña nueva de la app.
    assert sup.llamadas[1][2].endswith("/nueva-contrasena")

    assert len(correo.enviados) == 1
    enviado = correo.enviados[0]
    assert enviado["to"] == "admin@cliente.ec"
    assert enviado["empresa"] == "Comercial Andina S.A."
    assert "Presupuestos" in enviado["herramienta"]
    assert enviado["enlace"].startswith("https://supabase.local/verify?")
    # La firma nunca fija ni transporta una contraseña.
    assert "clave" not in enviado and "password" not in enviado


def test_alta_no_crea_la_empresa_en_la_app(db, cid, sup, correo):
    """[ADAPTATION] la empresa la crea el administrador al entrar (plan, regla 1)."""
    cuenta = _alta(db, cid)
    assert cuenta.empresa_id_app is None
    assert not any(c[0] in ("rpc", "insertar") for c in sup.llamadas)


def test_alta_deshace_el_usuario_si_falla_el_enlace(db, cid, sup, correo):
    sup.falla = "enlace_acceso"
    with pytest.raises(SupabaseAdminError):
        _alta(db, cid)

    assert ("borrar_usuario", "uid-admin@cliente.ec") in sup.llamadas
    assert sup.usuarios_vivos == set()
    assert correo.enviados == []
    db.rollback()
    assert db.query(AutCuenta).filter_by(client_id=cid).count() == 0


def test_alta_deshace_el_usuario_si_falla_el_correo(db, cid, sup, monkeypatch):
    fallido = FakeCorreo(resultado=None)  # send_email devuelve None si no pudo
    monkeypatch.setattr(
        service.email_mod,
        "send_automatizacion_acceso",
        fallido.send_automatizacion_acceso,
    )
    with pytest.raises(service.AutomatizacionError):
        _alta(db, cid)

    assert ("borrar_usuario", "uid-admin@cliente.ec") in sup.llamadas
    db.rollback()
    assert db.query(AutCuenta).filter_by(client_id=cid).count() == 0


def test_alta_duplicada_no_toca_supabase(db, cid, sup, correo):
    _alta(db, cid)
    sup.llamadas.clear()
    with pytest.raises(service.AutomatizacionError):
        _alta(db, cid, admin_email="otro@cliente.ec")
    assert sup.llamadas == []


# --- Regla 3: reenviar acceso -----------------------------------------------


def test_reenviar_acceso_genera_enlace_nuevo_y_lo_envia(db, cid, sup, correo):
    cuenta = _alta(db, cid)
    sup.llamadas.clear()
    correo.enviados.clear()

    service.reenviar_acceso(db, cuenta.id, actor=OPERADOR)

    assert [c[0] for c in sup.llamadas] == ["enlace_acceso"]
    assert len(correo.enviados) == 1
    assert "clave" not in correo.enviados[0]


def test_reenviar_acceso_de_cuenta_inexistente(db, sup, correo):
    with pytest.raises(service.AutomatizacionError):
        service.reenviar_acceso(db, 999999, actor=OPERADOR)


# --- Regla 4: baja reversible -----------------------------------------------


def test_suspender_y_reactivar(db, cid, sup, correo):
    cuenta = _alta(db, cid)

    service.suspender(db, cuenta.id, actor=OPERADOR)
    db.refresh(cuenta)
    assert cuenta.estado == "suspendida"
    assert ("bloquear_usuario", "uid-admin@cliente.ec", True) in sup.llamadas

    service.reactivar(db, cuenta.id, actor=OPERADOR)
    db.refresh(cuenta)
    assert cuenta.estado == "activa"
    assert ("bloquear_usuario", "uid-admin@cliente.ec", False) in sup.llamadas


# --- Regla 5: borrado con confirmación --------------------------------------


def test_borrar_sin_confirmar_no_borra_nada(db, cid, sup, correo):
    cuenta = _alta(db, cid)
    sup.llamadas.clear()

    with pytest.raises(service.AutomatizacionError):
        service.borrar(db, cuenta.id, actor=OPERADOR, confirmado=False)

    assert sup.llamadas == []
    assert db.get(AutCuenta, cuenta.id) is not None


def test_borrar_confirmado_borra_usuario_y_fila_pero_nada_de_la_app(db, cid, sup, correo):
    cuenta = _alta(db, cid)
    cuenta_id = cuenta.id
    sup.llamadas.clear()

    service.borrar(db, cuenta_id, actor=OPERADOR, confirmado=True)

    assert [c[0] for c in sup.llamadas] == ["borrar_usuario"]
    assert sup.usuarios_vivos == set()
    assert db.get(AutCuenta, cuenta_id) is None


# --- Regla 6: vigencia ------------------------------------------------------


def test_esta_vigente(db, cid):
    hoy = datetime.date.today()
    assert service.esta_vigente(AutCuenta(vigencia_hasta=None)) is True
    assert service.esta_vigente(AutCuenta(vigencia_hasta=hoy)) is True
    assert (
        service.esta_vigente(AutCuenta(vigencia_hasta=hoy - datetime.timedelta(days=1)))
        is False
    )


def test_listar_muestra_suspendida_la_cuenta_vencida_sin_tocar_datos(db, cid, sup, correo):
    ayer = datetime.date.today() - datetime.timedelta(days=1)
    cuenta = _alta(db, cid, vigencia_hasta=ayer)

    fila = [f for f in service.listar(db, client_id=cid)][0]
    assert fila["estado"] == "suspendida"
    assert fila["vencida"] is True

    db.refresh(cuenta)
    assert cuenta.estado == "activa"  # el dato guardado no cambió


# --- Regla 7: enlazar la empresa de la app ----------------------------------


def test_refrescar_empresa_guarda_el_id_cuando_aparece(db, cid, sup, correo):
    cuenta = _alta(db, cid)
    sup.miembros = [{"empresa_id": "11111111-2222-3333-4444-555555555555"}]

    assert service.refrescar_empresa(db, cuenta) == "11111111-2222-3333-4444-555555555555"
    db.refresh(cuenta)
    assert cuenta.empresa_id_app == "11111111-2222-3333-4444-555555555555"
    tabla, params = sup.llamadas[-1][1], sup.llamadas[-1][2]
    assert tabla == "empresa_miembros"
    assert params["email"] == "eq.admin@cliente.ec"


def test_refrescar_empresa_tolera_que_todavia_no_exista(db, cid, sup, correo):
    cuenta = _alta(db, cid)
    sup.miembros = []
    assert service.refrescar_empresa(db, cuenta) is None
    assert cuenta.empresa_id_app is None


def test_refrescar_empresa_tolera_que_supabase_falle(db, cid, sup, correo):
    cuenta = _alta(db, cid)
    sup.falla = "consultar"
    assert service.refrescar_empresa(db, cuenta) is None


# --- Regla 8: bitácora sin secretos -----------------------------------------


def test_cada_operacion_registra_actor_y_cuenta_sin_secretos(db, cid, sup, correo, caplog):
    with caplog.at_level(logging.INFO, logger=service.log.name):
        cuenta = _alta(db, cid)
        service.reenviar_acceso(db, cuenta.id, actor=OPERADOR)
        service.suspender(db, cuenta.id, actor=OPERADOR)
        service.reactivar(db, cuenta.id, actor=OPERADOR)
        service.borrar(db, cuenta.id, actor=OPERADOR, confirmado=True)

    texto = "\n".join(r.getMessage() for r in caplog.records)
    for accion in ("alta", "reenvio", "suspension", "reactivacion", "borrado"):
        assert accion in texto, f"falta registrar {accion}: {texto}"
    assert texto.count(OPERADOR) >= 5
    # Nunca un enlace de acceso, un token ni una llave.
    assert "token" not in texto.lower()
    assert "supabase.local/verify" not in texto
