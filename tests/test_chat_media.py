"""Tests del proxy de generación de imagen/video (backend → puente ComfyUI).

No se contacta ningún puente real: se mockea requests.post. Se valida que:
- /media/status refleja si el puente está configurado.
- /media/image y /media/video reenvían al puente y devuelven su JSON.
- sin configuración → 502; sin sesión → 401/403.
"""
import uuid

import pytest

from backend.app.auth import service as auth_service
from backend.app.auth.models import Role
from backend.app.chat import media
from backend.app.db.session import SessionLocal, init_db


@pytest.fixture(autouse=True)
def _db():
    init_db()
    yield


def _mk(role: Role = Role.user):
    email = f"{role.value}-{uuid.uuid4().hex[:8]}@example.com"
    db = SessionLocal()
    try:
        auth_service.create_user(db, email=email, password="Sup3rSecret!", role=role)
    finally:
        db.close()
    return email, "Sup3rSecret!"


def _login(client, email, pw):
    r = client.post("/api/v1/auth/login", data={"username": email, "password": pw})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


class _FakeResp:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload
        self.text = str(payload)

    def json(self):
        return self._payload


def _configure(monkeypatch, post_fn):
    monkeypatch.setattr(media, "_URL", "http://bridge.local")
    monkeypatch.setattr(media, "_KEY", "k")
    monkeypatch.setattr(media.requests, "post", post_fn)


def test_status_disabled_por_defecto(client, monkeypatch):
    monkeypatch.setattr(media, "_URL", "")
    monkeypatch.setattr(media, "_KEY", "")
    email, pw = _mk()
    tok = _login(client, email, pw)
    r = client.get("/api/v1/chat/media/status", headers=_h(tok))
    assert r.status_code == 200
    assert r.json() == {"enabled": False}


def test_status_enabled(client, monkeypatch):
    _configure(monkeypatch, lambda *a, **k: _FakeResp(200, {}))
    email, pw = _mk()
    tok = _login(client, email, pw)
    r = client.get("/api/v1/chat/media/status", headers=_h(tok))
    assert r.json() == {"enabled": True}


def test_image_proxy_ok(client, monkeypatch):
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["key"] = headers.get("X-Comfy-Key")
        return _FakeResp(200, {"model": "flux", "filename": "x.png", "seconds": 14.0,
                               "image_base64": "AAAA", "mime": "image/png"})

    _configure(monkeypatch, fake_post)
    email, pw = _mk()
    tok = _login(client, email, pw)
    r = client.post("/api/v1/chat/media/image", headers=_h(tok),
                    json={"prompt": "un gato", "model": "flux"})
    assert r.status_code == 200, r.text
    assert r.json()["image_base64"] == "AAAA"
    assert captured["url"].endswith("/generate")
    assert captured["json"]["prompt"] == "un gato"
    assert captured["key"] == "k"  # el backend inyecta la clave, no el cliente


def test_video_proxy_ok(client, monkeypatch):
    def fake_post(url, json=None, headers=None, timeout=None):
        assert url.endswith("/generate_video")
        return _FakeResp(200, {"model": "ltxv", "filename": "v.mp4", "seconds": 20.0,
                               "video_base64": "BBBB", "mime": "video/mp4"})

    _configure(monkeypatch, fake_post)
    email, pw = _mk()
    tok = _login(client, email, pw)
    r = client.post("/api/v1/chat/media/video", headers=_h(tok), json={"prompt": "ciudad"})
    assert r.status_code == 200, r.text
    assert r.json()["mime"] == "video/mp4"


def test_image_sin_config_da_502(client, monkeypatch):
    monkeypatch.setattr(media, "_URL", "")
    monkeypatch.setattr(media, "_KEY", "")
    email, pw = _mk()
    tok = _login(client, email, pw)
    r = client.post("/api/v1/chat/media/image", headers=_h(tok), json={"prompt": "x"})
    assert r.status_code == 502


def test_media_requiere_auth(client):
    assert client.get("/api/v1/chat/media/status").status_code in (401, 403)
    assert client.post("/api/v1/chat/media/image", json={"prompt": "x"}).status_code in (401, 403)
