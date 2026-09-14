import uuid

import pytest
from sqlalchemy import select

from backend.app.auth import service as auth_service
from backend.app.auth.models import Role
from backend.app.client_portal.rate_limit import reset_for_key
from backend.app.db.session import SessionLocal
from backend.app.recursos.models import RecursoLead
from backend.app.recursos.router import MSG_REGISTRO
from backend.app.recursos.tokens import crear_token

SLUG = "anticipo-ir-2026"
BASE = f"/api/v1/recursos/{SLUG}"


@pytest.fixture(autouse=True)
def enviados(monkeypatch):
    lista = []
    monkeypatch.setattr(
        "backend.app.recursos.notify.enviar_acceso", lambda lead_id: lista.append(lead_id)
    )
    return lista


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    reset_for_key("recurso-reg:testclient")
    reset_for_key("recurso-mail:global")
    yield
    reset_for_key("recurso-reg:testclient")
    reset_for_key("recurso-mail:global")


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


def test_registro_201_guarda_consentimiento_y_envia(client, enviados):
    p = _payload()
    r = client.post(f"{BASE}/registros", json=p)
    assert r.status_code == 201, r.text
    assert r.json() == {"ok": True, "mensaje": MSG_REGISTRO}
    [lead] = _leads(p["email"])
    assert lead.consentimiento_version == "v1"
    assert lead.consentimiento_at is not None
    assert enviados == [lead.id]


def test_registro_repetido_no_sobrescribe_y_reenvia(client, enviados):
    email = f"l-{uuid.uuid4().hex[:8]}@example.com"
    client.post(f"{BASE}/registros", json=_payload(email))
    r = client.post(f"{BASE}/registros", json=_payload(email.upper(), empresa="Otra S.A."))
    assert r.status_code == 201, r.text
    # Sin enumeración: la respuesta es idéntica a la de un correo nuevo.
    assert r.json() == {"ok": True, "mensaje": MSG_REGISTRO}
    [lead] = _leads(email)
    assert lead.empresa == "Empresa S.A."  # no se sobrescribe
    assert len(enviados) == 2


def test_limite_correo_por_email_no_envia_el_4to(client, enviados):
    email = f"l-{uuid.uuid4().hex[:8]}@example.com"
    for _ in range(3):
        r = client.post(f"{BASE}/registros", json=_payload(email))
        assert r.status_code == 201, r.text
    r4 = client.post(f"{BASE}/registros", json=_payload(email))
    assert r4.status_code == 201, r4.text
    assert r4.json() == {"ok": True, "mensaje": MSG_REGISTRO}  # sin señal al llamador
    assert len(enviados) == 3


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
    assert enviados == []


def test_recurso_desconocido_404(client):
    r = client.post("/api/v1/recursos/no-existe/registros", json=_payload())
    assert r.status_code == 404


def test_limite_429(client):
    ultimo = None
    for _ in range(11):
        ultimo = client.post(f"{BASE}/registros", json=_payload())
    assert ultimo.status_code == 429


def test_reenviar_no_revela_si_existe(client, enviados):
    email = f"l-{uuid.uuid4().hex[:8]}@example.com"
    client.post(f"{BASE}/registros", json=_payload(email))
    enviados.clear()
    existe = client.post(f"{BASE}/reenviar", json={"email": email.upper()})
    no_existe = client.post(f"{BASE}/reenviar", json={"email": "nadie-zz@example.com"})
    assert existe.status_code == no_existe.status_code == 200
    assert existe.json() == no_existe.json()
    assert len(enviados) == 1


def test_acceso_valido_marca_verificado(client):
    p = _payload()
    client.post(f"{BASE}/registros", json=p)
    [lead] = _leads(p["email"])
    r = client.get(f"{BASE}/acceso", params={"token": crear_token(lead.id, SLUG)})
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True, "nombre": "María Pérez"}
    assert _leads(p["email"])[0].verificado_at is not None


@pytest.mark.parametrize("caso", ["alterado", "vencido", "otro_recurso", "lead_inexistente"])
def test_acceso_invalido_401(client, caso):
    p = _payload()
    client.post(f"{BASE}/registros", json=p)
    [lead] = _leads(p["email"])
    bueno = crear_token(lead.id, SLUG)
    token = {
        "alterado": bueno[:-4] + ("AAAA" if not bueno.endswith("AAAA") else "BBBB"),
        "vencido": crear_token(lead.id, SLUG, dias=-1),
        "otro_recurso": crear_token(lead.id, "otro-recurso"),
        "lead_inexistente": crear_token(999_999_999, SLUG),
    }[caso]
    r = client.get(f"{BASE}/acceso", params={"token": token})
    assert r.status_code == 401


def test_token_de_recurso_no_abre_la_consola(client):
    r = client.get(
        "/api/v1/recursos/registros",
        headers={"Authorization": f"Bearer {crear_token(1, SLUG)}"},
    )
    assert r.status_code == 401


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
