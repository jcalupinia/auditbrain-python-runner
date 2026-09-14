import re
import uuid

import pytest
from sqlalchemy import select

from backend.app.auth import service as auth_service
from backend.app.auth.models import Role
from backend.app.client_portal.rate_limit import reset_for_key
from backend.app.db.session import SessionLocal
from backend.app.recursos.models import RecursoAcceso, RecursoCuenta, RecursoLead
from backend.app.recursos.router import MSG_REGISTRO

SLUG = "ir-personas-naturales-2026"
BASE = f"/api/v1/recursos/{SLUG}"
FORMATO_CLAVE = re.compile(r"^[ABCDEFGHJKMNPQRSTUVWXYZ23456789]{3}(-[ABCDEFGHJKMNPQRSTUVWXYZ23456789]{3}){2}$")


@pytest.fixture(autouse=True)
def enviados(monkeypatch):
    lista = []
    monkeypatch.setattr(
        "backend.app.recursos.notify.enviar_clave",
        lambda cuenta_id, clave, slug: lista.append((cuenta_id, clave, slug)),
    )
    return lista


_CLAVES_LIMITE = ("recurso-reg:testclient", "recurso-login-ip:testclient", "recurso-mail:global")


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    for k in _CLAVES_LIMITE:
        reset_for_key(k)
    yield
    for k in _CLAVES_LIMITE:
        reset_for_key(k)


def _payload(email=None, **cambios):
    d = {
        "nombre": "María Pérez",
        "empresa": "Empresa S.A.",
        "email": email or f"l-{uuid.uuid4().hex[:8]}@example.com",
        "acepta_politica": True,
    }
    d.update(cambios)
    return d


def _leads(email):
    db = SessionLocal()
    try:
        return list(
            db.execute(select(RecursoLead).where(RecursoLead.email == email.lower())).scalars()
        )
    finally:
        db.close()


def _cuenta(email):
    db = SessionLocal()
    try:
        c = db.execute(
            select(RecursoCuenta).where(RecursoCuenta.email == email.lower())
        ).scalar_one_or_none()
        if c is None:
            return None, set()
        accesos = set(
            db.execute(
                select(RecursoAcceso.recurso_slug).where(RecursoAcceso.cuenta_id == c.id)
            ).scalars()
        )
        db.expunge(c)
        return c, accesos
    finally:
        db.close()


def _admin_token(client):
    email = f"admin-{uuid.uuid4().hex[:8]}@example.com"
    pw = "Sup3rSecret!"
    db = SessionLocal()
    try:
        auth_service.create_user(db, email=email, password=pw, role=Role.admin)
    finally:
        db.close()
    r = client.post("/api/v1/auth/login", data={"username": email, "password": pw})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_registro_nuevo_crea_cuenta_acceso_y_envia_clave(client, enviados):
    p = _payload()
    r = client.post(f"{BASE}/registros", json=p)
    assert r.status_code == 201, r.text
    assert r.json() == {"ok": True, "mensaje": MSG_REGISTRO}
    [lead] = _leads(p["email"])
    assert lead.consentimiento_version == "v1"
    assert lead.consentimiento_at is not None
    cuenta, accesos = _cuenta(p["email"])
    assert cuenta is not None and cuenta.activo and cuenta.clave_generada
    assert accesos == {SLUG}
    [(cuenta_id, clave, slug)] = enviados
    assert cuenta_id == cuenta.id and slug == SLUG
    assert FORMATO_CLAVE.match(clave)
    assert clave.replace("-", "") not in cuenta.hashed_clave  # solo hash


def test_registro_repetido_rota_clave_con_respuesta_identica(client, enviados):
    email = f"l-{uuid.uuid4().hex[:8]}@example.com"
    client.post(f"{BASE}/registros", json=_payload(email))
    r = client.post(f"{BASE}/registros", json=_payload(email.upper(), empresa="Otra S.A."))
    assert r.status_code == 201, r.text
    # Sin enumeración: la respuesta es idéntica a la de un correo nuevo.
    assert r.json() == {"ok": True, "mensaje": MSG_REGISTRO}
    [lead] = _leads(email)
    assert lead.empresa == "Empresa S.A."  # no se sobrescribe
    assert len(enviados) == 2
    (id1, vieja, _), (id2, nueva, _) = enviados
    assert id1 == id2 and vieja != nueva
    login = lambda c: client.post(f"{BASE}/ingresar", json={"email": email, "clave": c})  # noqa: E731
    assert login(vieja).status_code == 401
    assert login(nueva).status_code == 200


def test_registro_en_recurso_cerrado_404(client, enviados):
    r = client.post("/api/v1/recursos/anticipo-ir-2026/registros", json=_payload())
    assert r.status_code == 404
    assert enviados == []


def test_limite_correo_por_email_no_envia_el_4to(client, enviados):
    email = f"l-{uuid.uuid4().hex[:8]}@example.com"
    for _ in range(3):
        r = client.post(f"{BASE}/registros", json=_payload(email))
        assert r.status_code == 201, r.text
    r4 = client.post(f"{BASE}/registros", json=_payload(email))
    assert r4.status_code == 201, r4.text
    assert r4.json() == {"ok": True, "mensaje": MSG_REGISTRO}  # sin señal al llamador
    assert len(enviados) == 3
    # La clave del último correo enviado sigue sirviendo (no se rotó sin enviar).
    r = client.post(f"{BASE}/ingresar", json={"email": email, "clave": enviados[-1][1]})
    assert r.status_code == 200, r.text


@pytest.mark.parametrize(
    "cambio",
    [
        {"acepta_politica": False},
        {"email": "no-es-correo"},
        {"nombre": "Al"},
        {"empresa": "   "},
    ],
)
def test_registro_invalido_422(client, cambio):
    r = client.post(f"{BASE}/registros", json=_payload(**cambio))
    assert r.status_code == 422, r.text


def test_honeypot_responde_ok_sin_guardar(client, enviados):
    p = _payload(website="http://spam.example")
    r = client.post(f"{BASE}/registros", json=p)
    assert r.status_code == 201
    assert r.json() == {"ok": True, "mensaje": MSG_REGISTRO}
    assert _leads(p["email"]) == []
    assert _cuenta(p["email"])[0] is None
    assert enviados == []


def test_recurso_desconocido_404(client):
    r = client.post("/api/v1/recursos/no-existe/registros", json=_payload())
    assert r.status_code == 404


def test_limite_429(client):
    ultimo = None
    for _ in range(11):
        ultimo = client.post(f"{BASE}/registros", json=_payload())
    assert ultimo.status_code == 429


def test_rutas_v1_eliminadas(client):
    assert client.get(f"{BASE}/acceso", params={"token": "x"}).status_code in (404, 405)
    assert client.post(f"{BASE}/reenviar", json={"email": "a@example.com"}).status_code in (404, 405)


def test_listado_sin_token_401(client):
    assert client.get("/api/v1/recursos/registros").status_code == 401


def test_listado_staff_200(client):
    p = _payload()
    client.post(f"{BASE}/registros", json=p)
    tok = _admin_token(client)
    r = client.get(
        "/api/v1/recursos/registros",
        params={"slug": SLUG},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 200, r.text
    fila = next(x for x in r.json() if x["email"] == p["email"])
    assert fila["recurso_slug"] == SLUG
    assert fila["empresa"] == "Empresa S.A."
