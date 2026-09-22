"""Tarea 3 del plan de Automatizaciones: cliente HTTP del Supabase de la app.

No hay ``responses`` ni ``requests_mock`` en los requirements del repo, así que
se simula el transporte parcheando ``requests.request`` dentro del módulo.
"""

import json
import logging

import pytest
import requests

from backend.app.automatizaciones import supabase_admin as sa

URL = "https://auditia.tail70d973.ts.net"
LLAVE = "service-role-llave-secretisima-123"


@pytest.fixture(autouse=True)
def _entorno(monkeypatch):
    monkeypatch.setenv("PRESUPUESTOS_SUPABASE_URL", URL)
    monkeypatch.setenv("PRESUPUESTOS_SERVICE_ROLE_KEY", LLAVE)
    # Sin esperas reales entre reintentos.
    monkeypatch.setattr(sa.time, "sleep", lambda _s: None)


class _Resp:
    def __init__(self, status=200, payload=None, text=None):
        self.status_code = status
        self._payload = payload
        if text is not None:
            self.text = text
        elif payload is not None:
            self.text = json.dumps(payload)
        else:
            self.text = ""

    def json(self):
        if self._payload is None:
            raise ValueError("sin cuerpo JSON")
        return self._payload


def _falso(monkeypatch, *respuestas):
    """Parchea ``requests.request`` devolviendo las respuestas en orden."""
    llamadas = []
    cola = list(respuestas)

    def _request(metodo, url, **kwargs):
        llamadas.append({"metodo": metodo, "url": url, **kwargs})
        item = cola.pop(0) if len(cola) > 1 else cola[0]
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(sa.requests, "request", _request)
    return llamadas


# --- Cabeceras y transporte -------------------------------------------------


def test_crear_usuario_metodo_ruta_cabeceras_y_id(monkeypatch):
    llamadas = _falso(monkeypatch, _Resp(200, {"id": "uuid-1", "email": "a@x.ec"}))

    datos = sa.crear_usuario("a@x.ec", "Ana")

    assert datos["id"] == "uuid-1"
    (c,) = llamadas
    assert c["metodo"] == "POST"
    assert c["url"] == f"{URL}/auth/v1/admin/users"
    assert c["headers"]["apikey"] == LLAVE
    assert c["headers"]["Authorization"] == f"Bearer {LLAVE}"
    assert c["timeout"] == 20
    assert c["json"] == {
        "email": "a@x.ec",
        "email_confirm": True,
        "user_metadata": {"nombre": "Ana"},
    }


def test_enlace_acceso_devuelve_action_link(monkeypatch):
    llamadas = _falso(
        monkeypatch, _Resp(200, {"action_link": "https://app.ec/#token=abc"})
    )

    enlace = sa.enlace_acceso("a@x.ec", "https://app.ec/clave")

    assert enlace == "https://app.ec/#token=abc"
    (c,) = llamadas
    assert c["metodo"] == "POST"
    assert c["url"] == f"{URL}/auth/v1/admin/generate_link"
    assert c["json"] == {
        "type": "recovery",
        "email": "a@x.ec",
        "redirect_to": "https://app.ec/clave",
    }


def test_enlace_acceso_sin_action_link_es_error(monkeypatch):
    _falso(monkeypatch, _Resp(200, {"otra_cosa": 1}))
    with pytest.raises(sa.SupabaseAdminError):
        sa.enlace_acceso("a@x.ec", "https://app.ec/clave")


@pytest.mark.parametrize(
    "bloquear,esperado", [(True, "876000h"), (False, "none")]
)
def test_bloquear_usuario(monkeypatch, bloquear, esperado):
    llamadas = _falso(monkeypatch, _Resp(200, {"id": "uuid-1"}))

    assert sa.bloquear_usuario("uuid-1", bloquear) is None

    (c,) = llamadas
    assert c["metodo"] == "PUT"
    assert c["url"] == f"{URL}/auth/v1/admin/users/uuid-1"
    assert c["json"] == {"ban_duration": esperado}


def test_borrar_usuario(monkeypatch):
    llamadas = _falso(monkeypatch, _Resp(200, text=""))

    assert sa.borrar_usuario("uuid-1") is None

    (c,) = llamadas
    assert c["metodo"] == "DELETE"
    assert c["url"] == f"{URL}/auth/v1/admin/users/uuid-1"


def test_rpc(monkeypatch):
    llamadas = _falso(monkeypatch, _Resp(200, {"empresa_id": "uuid-e"}))

    assert sa.rpc("crear_empresa_completa", {"nombre": "ACME"}) == {
        "empresa_id": "uuid-e"
    }

    (c,) = llamadas
    assert c["metodo"] == "POST"
    assert c["url"] == f"{URL}/rest/v1/rpc/crear_empresa_completa"
    assert c["json"] == {"nombre": "ACME"}


def test_consultar_envia_query_params(monkeypatch):
    llamadas = _falso(monkeypatch, _Resp(200, [{"id": 1}]))

    filas = sa.consultar("empresa_miembros", {"email": "eq.a@x.ec", "select": "*"})

    assert filas == [{"id": 1}]
    (c,) = llamadas
    assert c["metodo"] == "GET"
    assert c["url"] == f"{URL}/rest/v1/empresa_miembros"
    assert c["params"] == {"email": "eq.a@x.ec", "select": "*"}


def test_rpc_con_token_usuario_usa_llave_de_servicio_como_apikey_y_el_token_como_bearer(
    monkeypatch,
):
    """Tarea 9: las operaciones de membresía corren CON el token del propio
    administrador (para que ``es_admin_empresa`` etc. se apliquen como desde
    la app), pero el gateway sigue exigiendo una ``apikey`` válida del
    proyecto -> la de servicio."""
    llamadas = _falso(monkeypatch, _Resp(200, "miembro-uuid-1"))

    resultado = sa.rpc(
        "agregar_miembro", {"_empresa_id": "e1"}, token_usuario="token-del-admin"
    )

    assert resultado == "miembro-uuid-1"
    (c,) = llamadas
    assert c["headers"]["apikey"] == LLAVE
    assert c["headers"]["Authorization"] == "Bearer token-del-admin"


def test_rpc_sin_token_usuario_sigue_usando_la_llave_de_servicio(monkeypatch):
    llamadas = _falso(monkeypatch, _Resp(200, {"empresa_id": "uuid-e"}))

    sa.rpc("crear_empresa_completa", {"nombre": "ACME"})

    (c,) = llamadas
    assert c["headers"]["Authorization"] == f"Bearer {LLAVE}"


def test_consultar_con_token_usuario_usa_el_bearer_del_usuario(monkeypatch):
    llamadas = _falso(monkeypatch, _Resp(200, [{"id": 1}]))

    filas = sa.consultar(
        "empresa_miembros", {"select": "*"}, token_usuario="token-del-admin"
    )

    assert filas == [{"id": 1}]
    (c,) = llamadas
    assert c["headers"]["apikey"] == LLAVE
    assert c["headers"]["Authorization"] == "Bearer token-del-admin"


def test_insertar_pide_representacion(monkeypatch):
    llamadas = _falso(monkeypatch, _Resp(201, [{"id": 1}]))

    filas = sa.insertar("empresa_miembros", [{"email": "a@x.ec"}])

    assert filas == [{"id": 1}]
    (c,) = llamadas
    assert c["metodo"] == "POST"
    assert c["url"] == f"{URL}/rest/v1/empresa_miembros"
    assert c["headers"]["Prefer"] == "return=representation"
    assert c["json"] == [{"email": "a@x.ec"}]


def test_usuario_de_token_usa_el_bearer_del_usuario(monkeypatch):
    llamadas = _falso(monkeypatch, _Resp(200, {"id": "uuid-u", "email": "a@x.ec"}))

    datos = sa.usuario_de_token("token-del-admin")

    assert datos["email"] == "a@x.ec"
    (c,) = llamadas
    assert c["metodo"] == "GET"
    assert c["url"] == f"{URL}/auth/v1/user"
    assert c["headers"]["Authorization"] == "Bearer token-del-admin"
    assert c["headers"]["apikey"] == LLAVE


def test_usuario_de_token_invalido_lanza_error(monkeypatch):
    _falso(monkeypatch, _Resp(401, text='{"msg":"invalid token"}'))
    with pytest.raises(sa.SupabaseAdminError):
        sa.usuario_de_token("token-podrido")


# --- Reintentos y errores ---------------------------------------------------


def test_error_4xx_no_reintenta(monkeypatch):
    llamadas = _falso(monkeypatch, _Resp(422, text='{"msg":"ya existe"}'))

    with pytest.raises(sa.SupabaseAdminError) as exc:
        sa.crear_usuario("a@x.ec", "Ana")

    assert len(llamadas) == 1
    assert "422" in str(exc.value)
    assert "ya existe" in str(exc.value)


def test_error_4xx_expone_el_status_http(monkeypatch):
    """El router necesita distinguir un 4xx de GoTrue (correo ya registrado)
    de un fallo de red/5xx para poder devolver 409 en vez de 502."""
    _falso(monkeypatch, _Resp(422, text='{"msg":"ya existe"}'))
    with pytest.raises(sa.SupabaseAdminError) as exc:
        sa.crear_usuario("a@x.ec", "Ana")
    assert exc.value.status == 422


def test_error_5xx_reintenta_dos_veces_y_lanza(monkeypatch):
    llamadas = _falso(monkeypatch, _Resp(503, text="upstream caído"))

    with pytest.raises(sa.SupabaseAdminError) as exc:
        sa.crear_usuario("a@x.ec", "Ana")

    assert len(llamadas) == 3  # intento inicial + 2 reintentos
    assert "503" in str(exc.value)


def test_error_5xx_agotado_no_expone_status_4xx(monkeypatch):
    """Un 5xx agotado es un fallo de infraestructura (502), no un 409."""
    _falso(monkeypatch, _Resp(503, text="upstream caído"))
    with pytest.raises(sa.SupabaseAdminError) as exc:
        sa.crear_usuario("a@x.ec", "Ana")
    assert exc.value.status is None


def test_error_de_red_no_expone_status_4xx(monkeypatch):
    _falso(monkeypatch, requests.ConnectionError("sin ruta al host"))
    with pytest.raises(sa.SupabaseAdminError) as exc:
        sa.borrar_usuario("uuid-1")
    assert exc.value.status is None


def test_error_5xx_se_recupera_en_el_reintento(monkeypatch):
    llamadas = _falso(
        monkeypatch, _Resp(500, text="boom"), _Resp(200, {"id": "uuid-1"})
    )

    assert sa.crear_usuario("a@x.ec", "Ana")["id"] == "uuid-1"
    assert len(llamadas) == 2


def test_error_de_red_reintenta_y_lanza(monkeypatch):
    llamadas = _falso(monkeypatch, requests.ConnectionError("sin ruta al host"))

    with pytest.raises(sa.SupabaseAdminError):
        sa.borrar_usuario("uuid-1")

    assert len(llamadas) == 3


def test_cuerpo_del_error_truncado_a_200(monkeypatch):
    _falso(monkeypatch, _Resp(400, text="X" * 5000))

    with pytest.raises(sa.SupabaseAdminError) as exc:
        sa.rpc("lo_que_sea", {})

    assert "X" * 200 in str(exc.value)
    assert "X" * 201 not in str(exc.value)


# --- Token vacío nunca cae silenciosamente en la llave de servicio ---------


def test_bearer_vacio_lanza_en_vez_de_usar_la_llave_de_servicio(monkeypatch):
    """``bearer=""`` (p. ej. un token de sesión vacío) NO debe caer en
    ``bearer or llave`` y colarse como si fuera la llave de servicio."""
    llamadas = _falso(monkeypatch, _Resp(200, {"id": "uuid-u"}))
    with pytest.raises(sa.SupabaseAdminError):
        sa._pedir("GET", "/auth/v1/user", bearer="")
    assert llamadas == []  # nunca llegó a golpear la red con la llave de respaldo


def test_bearer_none_si_usa_la_llave_de_servicio(monkeypatch):
    """``bearer=None`` (el default) sigue siendo el uso intencional de la
    llave de servicio; solo la cadena vacía explícita es el bug."""
    llamadas = _falso(monkeypatch, _Resp(200, {"id": "uuid-u"}))
    sa._pedir("GET", "/auth/v1/user", bearer=None)
    (c,) = llamadas
    assert c["headers"]["Authorization"] == f"Bearer {LLAVE}"


# --- Configuración faltante -------------------------------------------------


@pytest.mark.parametrize(
    "faltante", ["PRESUPUESTOS_SUPABASE_URL", "PRESUPUESTOS_SERVICE_ROLE_KEY"]
)
def test_falta_variable_de_entorno(monkeypatch, faltante):
    monkeypatch.delenv(faltante)
    with pytest.raises(sa.SupabaseAdminError) as exc:
        sa.crear_usuario("a@x.ec", "Ana")
    mensaje = str(exc.value)
    assert faltante in mensaje
    assert "configur" in mensaje.lower()  # mensaje en español, accionable


# --- La llave nunca se filtra -----------------------------------------------


def test_la_llave_nunca_aparece_en_logs_ni_en_el_error(monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    _falso(monkeypatch, _Resp(500, text="boom"))

    with pytest.raises(sa.SupabaseAdminError) as exc:
        sa.crear_usuario("a@x.ec", "Ana")

    assert LLAVE not in caplog.text
    assert "apikey" not in caplog.text.lower()
    assert LLAVE not in str(exc.value)
    assert LLAVE not in repr(exc.value)


def test_la_llave_tampoco_se_filtra_en_error_de_red(monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    _falso(monkeypatch, requests.ConnectionError(f"fallo con apikey {LLAVE}"))

    with pytest.raises(sa.SupabaseAdminError) as exc:
        sa.usuario_de_token("token-del-admin")

    assert LLAVE not in caplog.text
    assert LLAVE not in str(exc.value)
    assert "token-del-admin" not in caplog.text
    assert "token-del-admin" not in str(exc.value)
