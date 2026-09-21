"""Tests del emisor del permiso para el Motor de Auditoría Analítica (AUD, staff)."""
import uuid

import jwt

from backend.app.auth import service as auth_service
from backend.app.auth.models import Role
from backend.app.db.session import SessionLocal, init_db

URL = "/api/v1/aud/motor-analitico/permiso"
CLAVE = "k" * 40
MOTOR = "https://auditia.tail70d973.ts.net:8443/motor"


def _mk_user(role=Role.user):
    init_db()
    email = f"ma-{uuid.uuid4().hex[:6]}@ex.com"
    db = SessionLocal()
    try:
        auth_service.create_user(db, email=email, password="Sup3rSecret!", role=role)
    finally:
        db.close()
    return email


def _token(client, email):
    r = client.post("/api/v1/auth/login", data={"username": email, "password": "Sup3rSecret!"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_sin_sesion_rechazado(client):
    r = client.post(URL, json={"encargo": "ENC-1", "accion": "ejecutar"})
    assert r.status_code in (401, 403)


def test_sin_configuracion_503(client, monkeypatch):
    monkeypatch.delenv("MOTOR_TOKEN_SECRET", raising=False)
    monkeypatch.delenv("MOTOR_ANALITICO_URL", raising=False)
    r = client.post(URL, json={"encargo": "ENC-1", "accion": "ejecutar"},
                    headers=_token(client, _mk_user()))
    assert r.status_code == 503


def test_emite_permiso_de_vida_corta(client, monkeypatch):
    monkeypatch.setenv("MOTOR_TOKEN_SECRET", CLAVE)
    monkeypatch.setenv("MOTOR_ANALITICO_URL", MOTOR + "/")
    email = _mk_user()
    r = client.post(URL, json={"encargo": "ENC-1", "accion": "ejecutar"},
                    headers=_token(client, email))
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["url"] == MOTOR and cuerpo["expira_en"] == 300
    datos = jwt.decode(cuerpo["token"], CLAVE, algorithms=["HS256"], audience="motor-analitico",
                       options={"require": ["exp", "iat", "sub", "aud"]})
    assert datos["sub"] == email and datos["role"] == "user"
    assert (datos["encargo"], datos["accion"]) == ("ENC-1", "ejecutar")
    assert datos["exp"] - datos["iat"] == 300


def test_accion_invalida_422(client, monkeypatch):
    monkeypatch.setenv("MOTOR_TOKEN_SECRET", CLAVE)
    monkeypatch.setenv("MOTOR_ANALITICO_URL", MOTOR)
    r = client.post(URL, json={"encargo": "ENC-1", "accion": "borrar"},
                    headers=_token(client, _mk_user()))
    assert r.status_code == 422


def test_cliente_de_portal_no_obtiene_permiso(client, monkeypatch):
    """require_staff (via get_current_user) excluye Role.client (defensa:
    el portal cliente nunca debe poder pedir un permiso para el Motor de
    Auditoría Analítica). get_current_user ya rechaza el rol client con 401
    antes de llegar al chequeo de rol de require_staff (403), así que ambos
    códigos son válidos aquí."""
    monkeypatch.setenv("MOTOR_TOKEN_SECRET", CLAVE)
    monkeypatch.setenv("MOTOR_ANALITICO_URL", MOTOR)
    email = _mk_user(Role.client)
    r = client.post(URL, json={"encargo": "ENC-1", "accion": "ejecutar"},
                    headers=_token(client, email))
    assert r.status_code in (401, 403), r.text
