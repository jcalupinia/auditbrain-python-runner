"""Recursos v2: clave personal, login por recurso, olvidé mi clave y gestión staff."""

import datetime
import uuid

import pytest
from sqlalchemy import select

from backend.app.auth import service as auth_service
from backend.app.auth.models import Role
from backend.app.client_portal.rate_limit import reset_for_key
from backend.app.db.session import SessionLocal
from backend.app.recursos.claves import ALFABETO, generar_clave, normalizar
from backend.app.recursos.models import RecursoAcceso, RecursoCuenta, RecursoLead

PN = "ir-personas-naturales-2026"
ANT = "anticipo-ir-2026"
API = "/api/v1/recursos"
MSG_401 = "Usuario o clave incorrectos."
MSG_403 = (
    "Su usuario aún no tiene acceso a esta herramienta. Solicítelo por WhatsApp "
    "0990 609 811 o a jcalupinia@auditconsulting.ec."
)
IP_KEY = "recurso-reg:testclient"
LOGIN_IP_KEY = "recurso-login-ip:testclient"


@pytest.fixture(autouse=True)
def enviados(monkeypatch):
    lista = []
    monkeypatch.setattr(
        "backend.app.recursos.notify.enviar_clave",
        lambda cuenta_id, clave, slug: lista.append((cuenta_id, clave, slug)),
    )
    return lista


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    for k in (IP_KEY, LOGIN_IP_KEY, "recurso-mail:global"):
        reset_for_key(k)
    yield
    for k in (IP_KEY, LOGIN_IP_KEY, "recurso-mail:global"):
        reset_for_key(k)


def _email():
    return f"c-{uuid.uuid4().hex[:8]}@example.com"


def _registrar(client, enviados, email=None):
    email = email or _email()
    r = client.post(
        f"{API}/{PN}/registros",
        json={"nombre": "Ana Torres", "empresa": "Alfa S.A.", "email": email, "acepta_politica": True},
    )
    assert r.status_code == 201, r.text
    cuenta_id, clave, _ = enviados[-1]
    return email, cuenta_id, clave


def _ingresar(client, email, clave, slug=PN):
    reset_for_key(LOGIN_IP_KEY)  # aísla el límite por correo del límite por IP
    return client.post(f"{API}/{slug}/ingresar", json={"email": email, "clave": clave})


def _token(client, role):
    email = f"{role.value}-{uuid.uuid4().hex[:8]}@example.com"
    pw = "Sup3rSecret!"
    db = SessionLocal()
    try:
        auth_service.create_user(db, email=email, password=pw, role=role)
    finally:
        db.close()
    r = client.post("/api/v1/auth/login", data={"username": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ---- clave ---------------------------------------------------------------

def test_generar_clave_formato_y_alfabeto():
    vistas = set()
    for _ in range(200):
        c = generar_clave()
        assert len(c) == 11 and c[3] == "-" and c[7] == "-"
        assert all(ch in ALFABETO for ch in c.replace("-", ""))
        vistas.add(c)
    assert len(vistas) == 200
    assert not set("O0I1L") & set(ALFABETO)


def test_normalizar():
    assert normalizar(" abc-def ghj ") == "ABCDEFGHJ"


# ---- ingresar ------------------------------------------------------------

def test_ingresar_200_actualiza_ultimo_ingreso_y_verifica_lead(client, enviados):
    email, cuenta_id, clave = _registrar(client, enviados)
    r = _ingresar(client, email.upper(), clave)
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True, "nombre": "Ana Torres"}
    db = SessionLocal()
    try:
        assert db.get(RecursoCuenta, cuenta_id).ultimo_ingreso_at is not None
        lead = db.execute(select(RecursoLead).where(RecursoLead.email == email)).scalar_one()
        assert lead.verificado_at is not None
    finally:
        db.close()


@pytest.mark.parametrize("variante", [str.lower, lambda c: c.replace("-", ""), lambda c: c.replace("-", " ")])
def test_ingresar_clave_generada_tolerante(client, enviados, variante):
    email, _, clave = _registrar(client, enviados)
    assert _ingresar(client, email, variante(clave)).status_code == 200


def test_ingresar_clave_errada_o_cuenta_inexistente_401(client, enviados):
    email, _, _ = _registrar(client, enviados)
    for e, c in ((email, "AAA-AAA-AAA"), (_email(), "AAA-AAA-AAA")):
        r = _ingresar(client, e, c)
        assert r.status_code == 401
        assert r.json()["detail"] == MSG_401


def test_ingresar_anticipo_sin_acceso_403(client, enviados):
    email, _, clave = _registrar(client, enviados)
    r = _ingresar(client, email, clave, slug=ANT)
    assert r.status_code == 403
    assert r.json()["detail"] == MSG_403


def test_ingresar_recurso_desconocido_404(client):
    assert _ingresar(client, _email(), "x", slug="no-existe").status_code == 404


def test_ingresar_11_fallos_del_mismo_correo_429(client, enviados):
    email, _, clave = _registrar(client, enviados)
    for _ in range(10):
        assert _ingresar(client, email, "MAL-MAL-MAL").status_code == 401
    assert _ingresar(client, email, "MAL-MAL-MAL").status_code == 429
    # Con el correo bloqueado ni la clave correcta pasa (sin oráculo).
    assert _ingresar(client, email, clave).status_code == 429
    reset_for_key(f"recurso-login:{email}")


def test_ingresar_exito_reinicia_contador_de_fallos(client, enviados):
    email, _, clave = _registrar(client, enviados)
    for _ in range(9):
        _ingresar(client, email, "MAL-MAL-MAL")
    assert _ingresar(client, email, clave).status_code == 200
    for _ in range(9):
        assert _ingresar(client, email, "MAL-MAL-MAL").status_code == 401


def test_ingresar_limite_por_ip_propio_30(client, enviados):
    email, _, clave = _registrar(client, enviados)
    # 30 ingresos desde la misma IP pasan (el de registros, 10/10 min, no aplica)...
    for i in range(30):
        r = client.post(f"{API}/{PN}/ingresar", json={"email": email, "clave": clave})
        assert r.status_code == 200, (i, r.text)
    # ...el 31 no.
    r = client.post(f"{API}/{PN}/ingresar", json={"email": email, "clave": clave})
    assert r.status_code == 429
    assert r.json()["detail"] == "Demasiados intentos desde esta red. Intente en unos minutos."


def test_ingresar_cuenta_inexistente_corre_bcrypt(client, monkeypatch):
    from backend.app.recursos import service

    llamadas = []
    real = service.verify_password
    monkeypatch.setattr(service, "verify_password", lambda p, h: llamadas.append(h) or real(p, h))
    r = _ingresar(client, _email(), "")
    assert r.status_code == 422  # clave vacía no llega al servicio
    r = _ingresar(client, _email(), "---")
    assert r.status_code == 401 and r.json()["detail"] == MSG_401
    assert llamadas == [service._HASH_SENUELO]


def test_registro_en_cuenta_desactivada_no_envia_ni_rota(client, enviados):
    email, cuenta_id, clave = _registrar(client, enviados)
    h = _token(client, Role.admin)
    client.post(f"{API}/cuentas/{cuenta_id}/activo", json={"activo": False}, headers=h)
    db = SessionLocal()
    try:
        antes = db.get(RecursoCuenta, cuenta_id).hashed_clave
    finally:
        db.close()
    r = client.post(
        f"{API}/{PN}/registros",
        json={"nombre": "Ana Torres", "empresa": "Alfa S.A.", "email": email, "acepta_politica": True},
    )
    assert r.status_code == 201
    assert len(enviados) == 1
    db = SessionLocal()
    try:
        cuenta = db.get(RecursoCuenta, cuenta_id)
        assert cuenta.hashed_clave == antes and cuenta.activo is False
    finally:
        db.close()


# ---- olvidé mi clave -----------------------------------------------------

def test_olvide_clave_cuenta_existente_rota(client, enviados):
    email, cuenta_id, vieja = _registrar(client, enviados)
    r = client.post(f"{API}/{PN}/olvide-clave", json={"email": email.upper()})
    assert r.status_code == 200
    assert len(enviados) == 2
    assert enviados[-1][0] == cuenta_id and enviados[-1][2] == PN
    nueva = enviados[-1][1]
    assert _ingresar(client, email, vieja).status_code == 401
    assert _ingresar(client, email, nueva).status_code == 200


def test_olvide_clave_lead_sin_cuenta_crea_cuenta(client, enviados):
    email = _email()
    db = SessionLocal()
    try:
        db.add(
            RecursoLead(
                recurso_slug=PN, nombre="Luis Mora", empresa="Beta", email=email,
                consentimiento_at=datetime.datetime(2026, 9, 1), consentimiento_version="v1",
            )
        )
        db.commit()
    finally:
        db.close()
    r = client.post(f"{API}/{PN}/olvide-clave", json={"email": email})
    assert r.status_code == 200
    [(cuenta_id, clave, slug)] = enviados
    db = SessionLocal()
    try:
        accesos = set(
            db.execute(
                select(RecursoAcceso.recurso_slug).where(RecursoAcceso.cuenta_id == cuenta_id)
            ).scalars()
        )
    finally:
        db.close()
    assert accesos == {PN}
    r = _ingresar(client, email, clave)
    assert r.status_code == 200 and r.json()["nombre"] == "Luis Mora"


def test_olvide_clave_inexistente_respuesta_generica(client, enviados):
    email, _, _ = _registrar(client, enviados)
    enviados.clear()
    existe = client.post(f"{API}/{PN}/olvide-clave", json={"email": email})
    no_existe = client.post(f"{API}/{PN}/olvide-clave", json={"email": _email()})
    assert existe.status_code == no_existe.status_code == 200
    assert existe.json() == no_existe.json()
    assert len(enviados) == 1


# ---- staff ---------------------------------------------------------------

def test_cuentas_sin_token_401(client):
    assert client.get(f"{API}/cuentas").status_code == 401
    assert client.put(f"{API}/cuentas/1/accesos/{ANT}").status_code == 401


def test_operador_lista_pero_no_modifica(client, enviados):
    email, cuenta_id, _ = _registrar(client, enviados)
    h = _token(client, Role.user)
    r = client.get(f"{API}/cuentas", headers=h)
    assert r.status_code == 200, r.text
    fila = next(x for x in r.json() if x["email"] == email)
    assert fila["id"] == cuenta_id
    assert fila["nombre"] == "Ana Torres" and fila["empresa"] == "Alfa S.A."
    assert fila["accesos"] == [PN] and fila["activo"] is True
    assert fila["consentimiento_at"] is not None and "email_enviado" in fila
    assert "hashed_clave" not in fila
    for metodo, ruta, body in (
        ("put", f"/cuentas/{cuenta_id}/accesos/{ANT}", None),
        ("delete", f"/cuentas/{cuenta_id}/accesos/{PN}", None),
        ("post", f"/cuentas/{cuenta_id}/reset-clave", {"enviar_correo": False}),
        ("post", f"/cuentas/{cuenta_id}/activo", {"activo": False}),
    ):
        kw = {"headers": h} | ({"json": body} if body is not None else {})
        assert getattr(client, metodo)(f"{API}{ruta}", **kw).status_code == 403


def test_admin_otorga_y_quita_acceso(client, enviados):
    email, cuenta_id, clave = _registrar(client, enviados)
    h = _token(client, Role.admin)
    r = client.put(f"{API}/cuentas/{cuenta_id}/accesos/{ANT}", headers=h)
    assert r.status_code == 200, r.text
    assert sorted(r.json()["accesos"]) == sorted([PN, ANT])
    assert client.put(f"{API}/cuentas/{cuenta_id}/accesos/{ANT}", headers=h).status_code == 200  # idempotente
    db = SessionLocal()
    try:
        acc = db.execute(
            select(RecursoAcceso).where(
                RecursoAcceso.cuenta_id == cuenta_id, RecursoAcceso.recurso_slug == ANT
            )
        ).scalar_one()
        assert acc.otorgado_por.startswith("admin-")
    finally:
        db.close()
    assert _ingresar(client, email, clave, slug=ANT).status_code == 200
    r = client.delete(f"{API}/cuentas/{cuenta_id}/accesos/{ANT}", headers=h)
    assert r.status_code == 200 and r.json()["accesos"] == [PN]
    assert _ingresar(client, email, clave, slug=ANT).status_code == 403


def test_admin_acceso_404(client, enviados):
    _, cuenta_id, _ = _registrar(client, enviados)
    h = _token(client, Role.admin)
    assert client.put(f"{API}/cuentas/{cuenta_id}/accesos/no-existe", headers=h).status_code == 404
    assert client.put(f"{API}/cuentas/999999999/accesos/{ANT}", headers=h).status_code == 404
    assert client.post(f"{API}/cuentas/999999999/activo", json={"activo": False}, headers=h).status_code == 404


def test_reset_con_clave_escrita_se_compara_exacta(client, enviados):
    email, cuenta_id, vieja = _registrar(client, enviados)
    h = _token(client, Role.admin)
    r = client.post(
        f"{API}/cuentas/{cuenta_id}/reset-clave",
        json={"new_password": "MiClave-2026", "enviar_correo": False},
        headers=h,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["email"] == email and body["temp_password"] == "MiClave-2026"
    assert body["note"] == "Comparta esta clave con la persona por un canal seguro. No se vuelve a mostrar."
    assert len(enviados) == 1  # no se envió correo
    assert _ingresar(client, email, vieja).status_code == 401
    assert _ingresar(client, email, "miclave-2026").status_code == 401
    assert _ingresar(client, email, "MiClave2026").status_code == 401
    assert _ingresar(client, email, "MiClave-2026").status_code == 200


def test_reset_sin_clave_genera_y_envia(client, enviados):
    email, cuenta_id, _ = _registrar(client, enviados)
    h = _token(client, Role.admin)
    r = client.post(f"{API}/cuentas/{cuenta_id}/reset-clave", json={"enviar_correo": True}, headers=h)
    assert r.status_code == 200, r.text
    nueva = r.json()["temp_password"]
    assert len(nueva) == 11 and nueva[3] == "-"
    assert enviados[-1] == (cuenta_id, nueva, PN)
    assert _ingresar(client, email, nueva.lower()).status_code == 200


@pytest.mark.parametrize("clave", ["corta", "a" * 73, "ñ" * 37])  # "ñ"*37 = 74 bytes
def test_reset_clave_fuera_de_rango_422(client, enviados, clave):
    _, cuenta_id, _ = _registrar(client, enviados)
    h = _token(client, Role.admin)
    r = client.post(
        f"{API}/cuentas/{cuenta_id}/reset-clave", json={"new_password": clave, "enviar_correo": False}, headers=h
    )
    assert r.status_code == 422


def test_reset_con_correo_sin_accesos_no_envia(client, enviados):
    _, cuenta_id, _ = _registrar(client, enviados)
    h = _token(client, Role.admin)
    client.delete(f"{API}/cuentas/{cuenta_id}/accesos/{PN}", headers=h)
    r = client.post(f"{API}/cuentas/{cuenta_id}/reset-clave", json={"enviar_correo": True}, headers=h)
    assert r.status_code == 200 and r.json()["temp_password"]
    assert len(enviados) == 1  # solo el del registro


def test_desactivar_y_activar(client, enviados):
    email, cuenta_id, clave = _registrar(client, enviados)
    h = _token(client, Role.admin)
    r = client.post(f"{API}/cuentas/{cuenta_id}/activo", json={"activo": False}, headers=h)
    assert r.status_code == 200 and r.json() == {"ok": True, "activo": False}
    r = _ingresar(client, email, clave)
    assert r.status_code == 401 and r.json()["detail"] == MSG_401
    # Inactiva: olvidé mi clave no envía nada.
    enviados.clear()
    assert client.post(f"{API}/{PN}/olvide-clave", json={"email": email}).status_code == 200
    assert enviados == []
    client.post(f"{API}/cuentas/{cuenta_id}/activo", json={"activo": True}, headers=h)
    assert _ingresar(client, email, clave).status_code == 200
