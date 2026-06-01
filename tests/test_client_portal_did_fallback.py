"""Regresión: require_client_with_device debe aceptar el ``did`` claim del JWT
como fallback cuando el browser no envía la cookie ``device_id`` (caso
típico: Chrome incógnito + Privacy Sandbox bloquea cookies cross-site
entre subdominios bajo la Public Suffix List como *.onrender.com).

El JWT está firmado, así que ``did`` no es falsificable. El fingerprint
del dispositivo sigue validándose, manteniendo la unicidad por sesión.
"""
import uuid
import pytest

from backend.app.auth.jwt_tokens import create_access_token
from backend.app.auth.models import Role
from backend.app.auth.service import (
    create_user,
    get_user_by_email,
    start_new_session,
)
from backend.app.auth import device as device_mod
from backend.app.client_portal import service as cp_service
from backend.app.context.models import Client, Organization
from backend.app.db.session import SessionLocal


@pytest.fixture()
def db_session():
    db = SessionLocal()
    yield db
    db.close()


def _unique_email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"


@pytest.fixture()
def portal_user_with_device(db_session):
    """Crea Organization + Client + portal user + device registrado y
    devuelve (user, device, sid) listos para construir un JWT válido."""
    slug = f"org-{uuid.uuid4().hex[:6]}"
    org = Organization(name=f"O-{slug}", slug=slug, is_active=True)
    db_session.add(org); db_session.commit(); db_session.refresh(org)
    cli = Client(organization_id=org.id, name=f"C-{slug}", is_active=True)
    db_session.add(cli); db_session.commit(); db_session.refresh(cli)

    user, _temp = cp_service.create_portal_user(
        db_session, client_id=cli.id, email=_unique_email("did-fb")
    )
    # bypass password_reset_required para no obstaculizar el test
    user.password_reset_required = False
    db_session.commit(); db_session.refresh(user)

    fingerprint = device_mod.compute_fingerprint_hash(
        user_agent="TestUA", accept_language="en", accept_encoding="gzip"
    )
    device = device_mod.register_device(
        db_session, user=user, fingerprint_hash=fingerprint,
        user_agent="TestUA", ip="127.0.0.1",
    )
    sid = start_new_session(db_session, user=user)
    return user, device, sid, fingerprint


def _bearer_headers(user, sid, did, fingerprint):
    token = create_access_token(
        subject=user.email,
        role=Role.client.value,
        extra_claims={"sid": sid, "did": did},
    )
    # The fingerprint hash es derivado de estos tres headers; pasarlos
    # idénticos garantiza que validate_device matches.
    return {
        "Authorization": f"Bearer {token}",
        "User-Agent": "TestUA",
        "Accept-Language": "en",
        "Accept-Encoding": "gzip",
    }


def test_me_works_with_cookie_present(client, portal_user_with_device):
    """Path original: cookie device_id presente → debe autorizar."""
    user, device, sid, _fp = portal_user_with_device
    headers = _bearer_headers(user, sid, device.device_id, _fp)
    r = client.get(
        "/api/v1/client/auth/me",
        headers=headers,
        cookies={"device_id": device.device_id},
    )
    assert r.status_code == 200, r.text


def test_me_works_with_did_fallback_when_cookie_missing(
    client, portal_user_with_device
):
    """Fallback nuevo: sin cookie pero con ``did`` en el JWT → debe autorizar."""
    user, device, sid, _fp = portal_user_with_device
    headers = _bearer_headers(user, sid, device.device_id, _fp)
    r = client.get(
        "/api/v1/client/auth/me",
        headers=headers,
        # NO cookies — simula browser que bloqueó la cookie cross-site
    )
    assert r.status_code == 200, r.text


def test_me_rejects_when_neither_cookie_nor_did(
    client, portal_user_with_device
):
    """Sin cookie y sin ``did`` en el JWT → 409 device_unauthorized."""
    user, device, sid, _fp = portal_user_with_device
    # JWT SIN did claim
    token = create_access_token(
        subject=user.email, role=Role.client.value,
        extra_claims={"sid": sid},  # did intencionalmente ausente
    )
    r = client.get(
        "/api/v1/client/auth/me",
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": "TestUA",
            "Accept-Language": "en",
            "Accept-Encoding": "gzip",
        },
    )
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "device_unauthorized"


def test_me_rejects_when_did_does_not_match_any_device(
    client, portal_user_with_device
):
    """``did`` en el JWT pero no existe device con ese id → 409."""
    user, _device, sid, _fp = portal_user_with_device
    headers = _bearer_headers(user, sid, "fake-device-id-not-registered", _fp)
    r = client.get("/api/v1/client/auth/me", headers=headers)
    assert r.status_code == 409
