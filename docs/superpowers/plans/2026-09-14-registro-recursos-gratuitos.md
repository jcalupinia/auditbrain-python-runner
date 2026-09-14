# Registro de recursos gratuitos — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que la Calculadora del Anticipo IR 2026 de `recursos.audit-ia.ec` solo se use tras registrar nombre, empresa y correo con consentimiento LOPDP, y que el acceso llegue por correo (enlace firmado).

**Architecture:** Módulo nuevo `backend/app/recursos/` en el portal (copia reducida de `backend/app/events/`): tabla `recurso_leads`, endpoints públicos con límite por IP, correo por Resend en `BackgroundTasks`, token JWT con `aud="recurso-acceso"`. Pestaña "REC" en la consola. En el mini-sitio estático, un recuadro que bloquea la calculadora hasta validar el enlace.

**Tech Stack:** FastAPI + SQLAlchemy 2 + PyJWT + Resend (backend), React/Vite (consola), HTML/JS plano (mini-sitio). Spec: `docs/superpowers/specs/2026-09-14-registro-recursos-gratuitos-design.md`.

**Repos y rutas:**
- Portal: worktree `C:\Users\jcalu\Desktop\PROYECTOS CLAUDE\ab-recursos-leads` (rama `feat/recursos-leads`, desde `origin/main` 948e989). Todos los comandos del portal se corren desde ahí.
- Mini-sitio: `C:\Users\jcalu\Desktop\PROYECTOS CLAUDE\audit-ia-recursos` (rama `main`, auto-deploy en Render — **no hacer push hasta la Tarea 9**).

---

## Mapa de archivos

Portal (crear):
- `backend/app/recursos/__init__.py` — vacío.
- `backend/app/recursos/catalog.py` — lista blanca de recursos + contacto.
- `backend/app/recursos/models.py` — `RecursoLead`.
- `backend/app/recursos/tokens.py` — `crear_token` / `leer_token`.
- `backend/app/recursos/schemas.py` — Pydantic.
- `backend/app/recursos/service.py` — alta idempotente, búsqueda, verificación, listado.
- `backend/app/recursos/notify.py` — envío del correo (background).
- `backend/app/recursos/router.py` — endpoints.
- `backend/app/notifications/templates/recurso_acceso.html` — plantilla del correo.
- `tests/test_recursos_tokens.py`, `tests/test_notifications_recurso_email.py`, `tests/test_recursos_router.py`.

Portal (modificar):
- `backend/app/db/session.py:154` — registrar modelos.
- `backend/app/api/__init__.py:21,45` — montar router.
- `backend/app/notifications/email.py` — `render_recurso_acceso` / `send_recurso_acceso`.
- `frontend/src/api.js` — `listRecursoLeads`.
- `frontend/src/App.jsx` — `_descargarCsv`, `RecursosLeads`, entrada en `OPS`, `case` en `render()`.

Mini-sitio (crear/modificar):
- `public/politica-datos/index.html` — política v1.
- `public/anticipo-ir-2026/index.html` — recuadro + script antes de `</body>`.
- `public/index.html` — texto de la tarjeta.

---

### Task 1: Catálogo, modelo y token

**Files:**
- Create: `backend/app/recursos/__init__.py`, `backend/app/recursos/catalog.py`, `backend/app/recursos/models.py`, `backend/app/recursos/tokens.py`
- Modify: `backend/app/db/session.py:154`
- Test: `tests/test_recursos_tokens.py`

- [ ] **Step 1: Write the failing test** — `tests/test_recursos_tokens.py`

```python
from backend.app.recursos.catalog import get_recurso
from backend.app.recursos.tokens import crear_token, leer_token

SLUG = "anticipo-ir-2026"


def test_catalogo_conoce_la_calculadora():
    rec = get_recurso(SLUG)
    assert rec is not None
    assert rec.url == "https://recursos.audit-ia.ec/anticipo-ir-2026/"
    assert get_recurso("no-existe") is None


def test_token_ida_y_vuelta():
    assert leer_token(crear_token(42, SLUG), SLUG) == 42


def test_token_de_otro_recurso_no_vale():
    assert leer_token(crear_token(42, "otro-recurso"), SLUG) is None


def test_token_vencido_no_vale():
    assert leer_token(crear_token(42, SLUG, dias=-1), SLUG) is None


def test_token_basura_no_vale():
    assert leer_token("no-es-un-token", SLUG) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_recursos_tokens.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.app.recursos'`

- [ ] **Step 3: Write minimal implementation**

`backend/app/recursos/__init__.py`: archivo vacío.

`backend/app/recursos/catalog.py`:

```python
"""Recursos gratuitos que requieren registro (lista blanca)."""

from __future__ import annotations

from dataclasses import dataclass

# Contacto de la firma para el correo y para ejercer derechos LOPDP
# (coincide con public/politica-datos/ del mini-sitio).
CONTACTO = "jcalupinia@auditconsulting.ec"


@dataclass(frozen=True)
class Recurso:
    slug: str
    titulo: str
    url: str


_RECURSOS = {
    r.slug: r
    for r in (
        Recurso(
            slug="anticipo-ir-2026",
            titulo="Calculadora del Anticipo IR 2026",
            url="https://recursos.audit-ia.ec/anticipo-ir-2026/",
        ),
    )
}


def get_recurso(slug: str) -> Recurso | None:
    return _RECURSOS.get(slug)
```

`backend/app/recursos/models.py`:

```python
"""Registros (leads) de recursos gratuitos."""

import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.session import Base


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


class RecursoLead(Base):
    __tablename__ = "recurso_leads"
    __table_args__ = (
        UniqueConstraint("recurso_slug", "email", name="uq_recurso_lead_slug_email"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recurso_slug: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(160), nullable=False)
    empresa: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(320), index=True, nullable=False)
    consentimiento_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    consentimiento_version: Mapped[str] = mapped_column(String(16), nullable=False)
    ip: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    email_enviado: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verificado_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False
    )
```

`backend/app/recursos/tokens.py`:

```python
"""Token del enlace de acceso a un recurso (JWT HS256, audiencia propia).

Lleva ``aud="recurso-acceso"``: ``auth.jwt_tokens.decode_token`` (consola) no
pasa ``audience``, así que PyJWT rechaza estos tokens allí. Un enlace de
recurso nunca sirve para entrar a la consola.
"""

from __future__ import annotations

import datetime

import jwt

from backend.app.auth.jwt_tokens import _ALGO, _secret

AUDIENCIA = "recurso-acceso"
TTL_DIAS = 30


def crear_token(lead_id: int, slug: str, *, dias: int = TTL_DIAS) -> str:
    ahora = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "sub": str(lead_id),
        "rs": slug,
        "aud": AUDIENCIA,
        "iat": ahora,
        "exp": ahora + datetime.timedelta(days=dias),
    }
    return jwt.encode(payload, _secret(), algorithm=_ALGO)


def leer_token(token: str, slug: str) -> int | None:
    """Id del lead si el token es válido, vigente y de este recurso; si no, None."""
    try:
        payload = jwt.decode(token, _secret(), algorithms=[_ALGO], audience=AUDIENCIA)
    except jwt.PyJWTError:
        return None
    if payload.get("rs") != slug:
        return None
    try:
        return int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        return None
```

`backend/app/db/session.py` — debajo de la línea `from backend.app.events import models as _events_models  # noqa: F401` agregar:

```python
    from backend.app.recursos import models as _recursos_models  # noqa: F401
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_recursos_tokens.py -q`
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/recursos backend/app/db/session.py tests/test_recursos_tokens.py
git commit -m "feat(recursos): catálogo, modelo RecursoLead y token de acceso"
```

---

### Task 2: Correo de acceso (plantilla + envío)

**Files:**
- Create: `backend/app/notifications/templates/recurso_acceso.html`, `backend/app/recursos/notify.py`
- Modify: `backend/app/notifications/email.py` (al final del archivo)
- Test: `tests/test_notifications_recurso_email.py`

- [ ] **Step 1: Write the failing test** — `tests/test_notifications_recurso_email.py`

```python
import datetime
import uuid

from backend.app.db.session import SessionLocal
from backend.app.notifications import email as email_mod
from backend.app.recursos import notify
from backend.app.recursos.models import RecursoLead
from backend.app.recursos.tokens import leer_token

SLUG = "anticipo-ir-2026"


def test_render_escapa_e_incluye_enlace():
    html = email_mod.render_recurso_acceso(
        nombre="<b>Ana</b>",
        titulo="Calculadora del Anticipo IR 2026",
        email="ana@example.com",
        enlace="https://recursos.audit-ia.ec/anticipo-ir-2026/?acceso=abc&x=1",
        contacto="jcalupinia@auditconsulting.ec",
    )
    assert "&lt;b&gt;Ana&lt;/b&gt;" in html
    assert "<b>Ana</b>" not in html
    assert 'href="https://recursos.audit-ia.ec/anticipo-ir-2026/?acceso=abc&amp;x=1"' in html
    assert "ana@example.com" in html
    assert "jcalupinia@auditconsulting.ec" in html


def test_notify_envia_enlace_valido_y_marca_enviado(monkeypatch):
    db = SessionLocal()
    try:
        lead = RecursoLead(
            recurso_slug=SLUG,
            nombre="Ana Torres",
            empresa="Alfa S.A.",
            email=f"n-{uuid.uuid4().hex[:8]}@example.com",
            consentimiento_at=datetime.datetime(2026, 9, 14),
            consentimiento_version="v1",
        )
        db.add(lead)
        db.commit()
        lead_id, correo = lead.id, lead.email
    finally:
        db.close()

    enviados = []
    monkeypatch.setattr(
        email_mod, "send_recurso_acceso", lambda **kw: enviados.append(kw) or {"id": "re_1"}
    )
    notify.enviar_acceso(lead_id)

    assert len(enviados) == 1
    kw = enviados[0]
    assert kw["to"] == correo
    prefijo = "https://recursos.audit-ia.ec/anticipo-ir-2026/?acceso="
    assert kw["enlace"].startswith(prefijo)
    assert leer_token(kw["enlace"][len(prefijo):], SLUG) == lead_id

    db = SessionLocal()
    try:
        assert db.get(RecursoLead, lead_id).email_enviado is True
    finally:
        db.close()


def test_notify_lead_inexistente_no_falla(monkeypatch):
    monkeypatch.setattr(email_mod, "send_recurso_acceso", lambda **kw: 1 / 0)
    notify.enviar_acceso(999_999_999)  # no debe lanzar
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_notifications_recurso_email.py -q`
Expected: FAIL — `AttributeError: module 'backend.app.notifications.email' has no attribute 'render_recurso_acceso'` (o `ImportError` de `notify`).

- [ ] **Step 3: Write minimal implementation**

`backend/app/notifications/templates/recurso_acceso.html`:

```html
<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:0;background:#f4f6f8">
  <div style="background:#0a2540;padding:24px;text-align:center">
    <h2 style="color:#fff;margin:0">AuditConsulting Group</h2>
    <p style="margin:6px 0 0;color:#9fb3c8;font-size:13px">Recursos gratuitos</p>
  </div>
  <div style="padding:24px;color:#0f172a">
    <p>Estimado(a) {{nombre}}:</p>
    <p>Gracias por registrarse. Su acceso a la <strong>{{titulo}}</strong> está listo.</p>
    <table style="width:100%;border-collapse:collapse;margin:16px 0;font-size:15px">
      <tr><td style="padding:6px 0;color:#64748b">Usuario</td><td style="padding:6px 0"><strong>{{email}}</strong></td></tr>
    </table>
    <p style="text-align:center;margin:20px 0">
      <a href="{{enlace}}" style="background:#C7A83C;color:#0a2540;font-weight:bold;padding:14px 30px;text-decoration:none;border-radius:6px;display:inline-block">Abrir mi calculadora</a>
    </p>
    <p style="color:#64748b;font-size:13px">El enlace es personal y vence en 30 días. Si vence, pida uno nuevo desde la misma página con la opción "¿Ya se registró?".</p>
    <p style="color:#334155;font-size:14px;margin-top:22px">¿Necesita revisar sus balances o su sistema de control interno? Escríbanos:<br>
      <strong>{{contacto}}</strong> · WhatsApp <strong>0990 609 811</strong></p>
    <p style="color:#94a3b8;font-size:11px;line-height:1.5;border-top:1px solid #e2e8f0;padding-top:14px;margin-top:24px">
      AuditConsulting Group trata sus datos (nombre, empresa y correo) para darle acceso a este recurso y enviarle información de la firma, con base en su consentimiento y conforme a la Ley Orgánica de Protección de Datos Personales del Ecuador. Puede ejercer sus derechos de acceso, rectificación, eliminación y oposición escribiendo a {{contacto}}.
    </p>
  </div>
</body>
</html>
```

`backend/app/notifications/email.py` — agregar al final:

```python
def render_recurso_acceso(
    *, nombre: str, titulo: str, email: str, enlace: str, contacto: str
) -> str:
    tpl = (_TEMPLATES_DIR / "recurso_acceso.html").read_text(encoding="utf-8")
    return (
        tpl.replace("{{enlace}}", _html.escape(enlace, quote=True))
        .replace("{{nombre}}", _html.escape(nombre))
        .replace("{{titulo}}", _html.escape(titulo))
        .replace("{{email}}", _html.escape(email))
        .replace("{{contacto}}", _html.escape(contacto))
    )


def send_recurso_acceso(
    *, to: str, nombre: str, titulo: str, enlace: str, contacto: str
) -> dict | None:
    html_body = render_recurso_acceso(
        nombre=nombre, titulo=titulo, email=to, enlace=enlace, contacto=contacto
    )
    return send_email(to=to, subject=f"Su acceso a la {titulo}", html=html_body)
```

`backend/app/recursos/notify.py`:

```python
"""Envío del correo de acceso (corre en BackgroundTask; nunca propaga)."""

from __future__ import annotations

import logging

from backend.app.db.session import SessionLocal
from backend.app.notifications import email as email_mod
from backend.app.recursos.catalog import CONTACTO, get_recurso
from backend.app.recursos.models import RecursoLead
from backend.app.recursos.tokens import crear_token

log = logging.getLogger(__name__)


def enviar_acceso(lead_id: int) -> None:
    db = SessionLocal()
    try:
        lead = db.get(RecursoLead, lead_id)
        rec = get_recurso(lead.recurso_slug) if lead else None
        if lead is None or rec is None:
            log.warning("Lead de recurso %s inexistente; no se envía correo.", lead_id)
            return
        enlace = f"{rec.url}?acceso={crear_token(lead.id, lead.recurso_slug)}"
        try:
            res = email_mod.send_recurso_acceso(
                to=lead.email,
                nombre=lead.nombre,
                titulo=rec.titulo,
                enlace=enlace,
                contacto=CONTACTO,
            )
            lead.email_enviado = res is not None
            db.commit()
        except Exception:  # noqa: BLE001
            log.exception("Correo de acceso falló para lead %s.", lead_id)
    finally:
        db.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_notifications_recurso_email.py -q`
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/notifications/templates/recurso_acceso.html backend/app/notifications/email.py backend/app/recursos/notify.py tests/test_notifications_recurso_email.py
git commit -m "feat(recursos): correo de acceso con enlace firmado"
```

---

### Task 3: Schemas, servicio y endpoints

**Files:**
- Create: `backend/app/recursos/schemas.py`, `backend/app/recursos/service.py`, `backend/app/recursos/router.py`
- Modify: `backend/app/api/__init__.py` (import junto a `events`; `include_router` después de `events_router`)
- Test: `tests/test_recursos_router.py`

- [ ] **Step 1: Write the failing test** — `tests/test_recursos_router.py`

```python
import uuid

import pytest
from sqlalchemy import select

from backend.app.auth import service as auth_service
from backend.app.auth.models import Role
from backend.app.client_portal.rate_limit import reset_for_key
from backend.app.db.session import SessionLocal
from backend.app.recursos.models import RecursoLead
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
    yield
    reset_for_key("recurso-reg:testclient")


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
    assert r.json()["ya_registrado"] is False
    [lead] = _leads(p["email"])
    assert lead.consentimiento_version == "v1"
    assert lead.consentimiento_at is not None
    assert enviados == [lead.id]


def test_registro_repetido_actualiza_y_reenvia(client, enviados):
    email = f"l-{uuid.uuid4().hex[:8]}@example.com"
    client.post(f"{BASE}/registros", json=_payload(email))
    r = client.post(f"{BASE}/registros", json=_payload(email.upper(), empresa="Otra S.A."))
    assert r.status_code == 201, r.text
    assert r.json()["ya_registrado"] is True
    [lead] = _leads(email)
    assert lead.empresa == "Otra S.A."
    assert len(enviados) == 2


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_recursos_router.py -q`
Expected: FAIL — respuestas 404 (ruta inexistente) en casi todos los tests.

- [ ] **Step 3: Write minimal implementation**

`backend/app/recursos/schemas.py`:

```python
"""Schemas Pydantic de recursos gratuitos."""

from __future__ import annotations

import datetime
from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, StringConstraints, field_validator

Nombre = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=160)]
Empresa = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class LeadCreate(BaseModel):
    nombre: Nombre
    empresa: Empresa
    email: EmailStr
    acepta_politica: bool
    # Campo trampa: invisible para personas; si llega con texto es un bot.
    website: str = Field(default="", max_length=200)

    @field_validator("acepta_politica")
    @classmethod
    def _debe_aceptar(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Debe aceptar la política de protección de datos.")
        return v


class ReenvioIn(BaseModel):
    email: EmailStr


class LeadResponse(BaseModel):
    ok: bool
    ya_registrado: bool
    mensaje: str


class MensajeOut(BaseModel):
    ok: bool
    mensaje: str


class AccesoOut(BaseModel):
    ok: bool
    nombre: str


class LeadOut(BaseModel):
    id: int
    recurso_slug: str
    nombre: str
    empresa: str
    email: str
    consentimiento_at: datetime.datetime
    consentimiento_version: str
    email_enviado: bool
    verificado_at: datetime.datetime | None
    created_at: datetime.datetime

    model_config = {"from_attributes": True}
```

`backend/app/recursos/service.py`:

```python
"""Lógica de negocio de los registros de recursos."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.recursos.models import RecursoLead, _utcnow
from backend.app.recursos.schemas import LeadCreate

# Versión del texto de public/politica-datos/ del mini-sitio.
POLITICA_VERSION = "v1"


def buscar(db: Session, slug: str, email: str) -> RecursoLead | None:
    return db.execute(
        select(RecursoLead).where(
            RecursoLead.recurso_slug == slug,
            RecursoLead.email == email.strip().lower(),
        )
    ).scalar_one_or_none()


def registrar(
    db: Session, *, slug: str, data: LeadCreate, ip: str
) -> tuple[RecursoLead, bool]:
    """Crea o actualiza el registro. Devuelve (lead, ya_registrado)."""
    email = str(data.email).strip().lower()
    lead = buscar(db, slug, email)
    ya_registrado = lead is not None
    if lead is None:
        lead = RecursoLead(recurso_slug=slug, email=email, ip=ip[:64])
        db.add(lead)
    lead.nombre = data.nombre
    lead.empresa = data.empresa
    lead.consentimiento_at = _utcnow()
    lead.consentimiento_version = POLITICA_VERSION
    try:
        db.commit()
    except IntegrityError:
        # Carrera: otra request insertó el mismo (slug, email) en paralelo.
        db.rollback()
        lead = buscar(db, slug, email)
        if lead is None:
            raise
        return lead, True
    db.refresh(lead)
    return lead, ya_registrado


def marcar_verificado(db: Session, lead: RecursoLead) -> None:
    if lead.verificado_at is None:
        lead.verificado_at = _utcnow()
        db.commit()


def listar(db: Session, *, slug: str | None = None, limit: int = 200) -> list[RecursoLead]:
    q = select(RecursoLead)
    if slug:
        q = q.where(RecursoLead.recurso_slug == slug)
    q = q.order_by(RecursoLead.created_at.desc(), RecursoLead.id.desc()).limit(limit)
    return list(db.execute(q).scalars())
```

`backend/app/recursos/router.py`:

```python
"""Endpoints /api/v1/recursos/* — registro público + acceso + listado staff."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from backend.app.auth.deps import require_staff
from backend.app.client_portal.rate_limit import check_and_record
from backend.app.db.session import get_db
from backend.app.events.router import _client_ip
from backend.app.recursos import notify, service
from backend.app.recursos.catalog import get_recurso
from backend.app.recursos.models import RecursoLead
from backend.app.recursos.schemas import (
    AccesoOut,
    LeadCreate,
    LeadOut,
    LeadResponse,
    MensajeOut,
    ReenvioIn,
)
from backend.app.recursos.tokens import leer_token

router = APIRouter(prefix="/recursos", tags=["recursos"])

MSG_REGISTRO = "Registro recibido. Le enviamos el enlace de acceso a su correo."
MSG_REENVIO = "Si el correo está registrado, le reenviamos el enlace de acceso."


def _recurso_o_404(slug: str) -> None:
    if get_recurso(slug) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Recurso no encontrado.")


def _limite(request: Request) -> str:
    ip = _client_ip(request)
    if not check_and_record(f"recurso-reg:{ip}", max_hits=10, window_seconds=600):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos desde esta red. Intente en unos minutos.",
        )
    return ip


@router.post(
    "/{slug}/registros", response_model=LeadResponse, status_code=status.HTTP_201_CREATED
)
def registrar_endpoint(
    slug: str,
    payload: LeadCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
):
    _recurso_o_404(slug)
    ip = _limite(request)
    if payload.website:  # bot: se le responde igual, sin guardar ni enviar
        return LeadResponse(ok=True, ya_registrado=False, mensaje=MSG_REGISTRO)
    lead, ya_registrado = service.registrar(db, slug=slug, data=payload, ip=ip)
    background_tasks.add_task(notify.enviar_acceso, lead.id)
    return LeadResponse(ok=True, ya_registrado=ya_registrado, mensaje=MSG_REGISTRO)


@router.post("/{slug}/reenviar", response_model=MensajeOut)
def reenviar_endpoint(
    slug: str,
    payload: ReenvioIn,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
):
    _recurso_o_404(slug)
    _limite(request)
    lead = service.buscar(db, slug, str(payload.email))
    if lead is not None:
        background_tasks.add_task(notify.enviar_acceso, lead.id)
    return MensajeOut(ok=True, mensaje=MSG_REENVIO)


@router.get("/{slug}/acceso", response_model=AccesoOut)
def acceso_endpoint(slug: str, token: str = Query(max_length=2000), db: Session = Depends(get_db)):
    _recurso_o_404(slug)
    lead_id = leer_token(token, slug)
    lead = db.get(RecursoLead, lead_id) if lead_id is not None else None
    if lead is None or lead.recurso_slug != slug:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail="Enlace inválido o vencido."
        )
    service.marcar_verificado(db, lead)
    return AccesoOut(ok=True, nombre=lead.nombre)


@router.get(
    "/registros", response_model=list[LeadOut], dependencies=[Depends(require_staff)]
)
def listar_endpoint(
    slug: str | None = None,
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    return [LeadOut.model_validate(r) for r in service.listar(db, slug=slug, limit=limit)]
```

`backend/app/api/__init__.py` — después de `from backend.app.events import router as events_router` agregar:

```python
from backend.app.recursos import router as recursos_router
```

y después de `api_router.include_router(events_router.router)` agregar:

```python
api_router.include_router(recursos_router.router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_recursos_router.py tests/test_recursos_tokens.py tests/test_notifications_recurso_email.py -q`
Expected: todos pasan (`26 passed`: 5 tokens + 3 correo + 18 router).

- [ ] **Step 5: Correr la suite completa del backend (no romper nada)**

Run: `python -m pytest tests/ -q --tb=short`
Expected: mismo resultado que en `origin/main` + los tests nuevos en verde. Si algo ya fallaba en `main`, comprobarlo con `git stash`-free: correr ese test en `../ab-of-facturacion` antes de atribuirlo a este cambio.

- [ ] **Step 6: Commit**

```bash
git add backend/app/recursos backend/app/api/__init__.py tests/test_recursos_router.py
git commit -m "feat(recursos): endpoints públicos de registro, reenvío y acceso + listado staff"
```

---

### Task 4: Pestaña "REC · Recursos" en la consola

**Files:**
- Modify: `frontend/src/api.js` (después de `listEventRegistrations`)
- Modify: `frontend/src/App.jsx` (`descargarInscritosCsv` ~l.1949, nuevo componente después de `Inscripciones()` ~l.2080, `OPS` ~l.2144, `render()` ~l.2180)

- [ ] **Step 1: api.js** — agregar después de `listEventRegistrations`:

```js
// ---------- Registros de recursos gratuitos (staff) ----------

export async function listRecursoLeads(limit = 1000) {
  return parse(
    await apiFetch(`${API_BASE}/api/v1/recursos/registros?limit=${limit}`, {
      headers: authHeaders(),
    })
  );
}
```

- [ ] **Step 2: App.jsx — extraer la descarga CSV** — reemplazar la función `descargarInscritosCsv` completa por:

```jsx
// Descarga filas como CSV (UTF-8 con BOM para que Excel lea los acentos).
function _descargarCsv(archivo, headers, filas) {
  const esc = (v) => {
    const s = String(v ?? "");
    return /[",\n;]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const lines = [headers.join(","), ...filas.map((f) => f.map(esc).join(","))];
  const blob = new Blob(["\uFEFF" + lines.join("\r\n")], {
    type: "text/csv;charset=utf-8;",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = archivo;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 30000);
}

function descargarInscritosCsv(rows) {
  _descargarCsv(
    "inscritos_charla_anexos.csv",
    ["Nombre", "Email", "Celular", "Cedula/RUC", "Empresa", "Fecha", "Email enviado", "Aviso enviado"],
    rows.map((r) => [
      r.nombre, r.email, r.telefono_e164, r.documento, r.empresa,
      _insFecha(r),
      r.email_enviado ? "si" : "no",
      r.aviso_interno_enviado ? "si" : "no",
    ])
  );
}
```

- [ ] **Step 3: App.jsx — componente nuevo** — pegar justo antes de `/* ---------------- Command Center Shell ---------------- */`:

```jsx
/* ---------------- Registros de recursos gratuitos (staff) ---------------- */
const REC_COLS = { gridTemplateColumns: "1.3fr 1.3fr 1.7fr 1.2fr 1.1fr 0.8fr" };

function RecursosLeads() {
  const [rows, setRows] = useState([]);
  const [busy, setBusy] = useState(true);
  const [err, setErr] = useState("");
  const [q, setQ] = useState("");

  const reload = useCallback(async () => {
    setBusy(true);
    setErr("");
    try {
      setRows(await api.listRecursoLeads());
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }, []);
  useEffect(() => {
    reload();
  }, [reload]);

  const term = q.trim().toLowerCase();
  const filtered = term
    ? rows.filter((r) =>
        `${r.nombre} ${r.email} ${r.empresa} ${r.recurso_slug}`.toLowerCase().includes(term)
      )
    : rows;
  const verificados = rows.filter((r) => r.verificado_at).length;
  const meta = term
    ? `${filtered.length} de ${rows.length}`
    : `${rows.length} registro(s) · ${verificados} verificado(s)`;

  const descargar = () =>
    _descargarCsv(
      "registros_recursos.csv",
      ["Nombre", "Empresa", "Email", "Recurso", "Fecha", "Verificado", "Email enviado"],
      filtered.map((r) => [
        r.nombre, r.empresa, r.email, r.recurso_slug, _insFecha(r),
        r.verificado_at ? "si" : "no",
        r.email_enviado ? "si" : "no",
      ])
    );

  return (
    <>
      <ViewHead code="REC" title="Registros de recursos gratuitos"
        sub="Personas que pidieron acceso a las herramientas de recursos.audit-ia.ec." />
      <Panel title="Registros" meta={meta}>
        <div className="row-form" style={{ marginBottom: 12 }}>
          <input
            placeholder="Buscar por nombre, email, empresa o recurso…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          <button className="btn ghost" onClick={reload} disabled={busy}>
            {busy ? "Cargando…" : "Actualizar"}
          </button>
          <button
            className="btn primary"
            onClick={descargar}
            disabled={busy || filtered.length === 0}
            title="Descargar la lista (se abre en Excel)"
          >
            ⇩ Descargar Excel/CSV
          </button>
        </div>
        {err && <div className="err">{err}</div>}
        {filtered.length > 0 ? (
          <div style={{ overflowX: "auto" }}>
            <div className="table" style={{ minWidth: 880 }}>
              <div className="tr th" style={REC_COLS}>
                <span>Nombre</span>
                <span>Empresa</span>
                <span>Email</span>
                <span>Recurso</span>
                <span>Fecha</span>
                <span>Estado</span>
              </div>
              {filtered.map((r) => (
                <div className="tr" key={r.id} style={REC_COLS}>
                  <span>{r.nombre}</span>
                  <span className="muted">{r.empresa}</span>
                  <span className="muted">{r.email}</span>
                  <span className="muted">{r.recurso_slug}</span>
                  <span className="muted">{_insFecha(r)}</span>
                  <span className="muted" title={r.verificado_at ? "Abrió el enlace del correo" : "Aún no abre el enlace"}>
                    {r.verificado_at ? "✅" : "—"}
                    {r.email_enviado ? " ✉️" : ""}
                  </span>
                </div>
              ))}
            </div>
          </div>
        ) : (
          !busy && (
            <div className="notice">
              {rows.length === 0 ? "Aún no hay registros." : "Sin resultados para la búsqueda."}
            </div>
          )
        )}
      </Panel>
    </>
  );
}
```

- [ ] **Step 4: App.jsx — navegación** — en `OPS`, después de la entrada `inscripciones`:

```jsx
    { id: "recursos", code: "REC", label: "Recursos", staff: true },
```

y en `render()`, después del `case "inscripciones": …`:

```jsx
      case "recursos":
        return isStaff ? <RecursosLeads /> : <Dashboard user={user} health={hp} />;
```

- [ ] **Step 5: Build**

Run: `cd frontend && npm ci && npm run build`
Expected: build sin errores (`✓ built in …`).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api.js frontend/src/App.jsx
git commit -m "feat(consola): pestaña REC con los registros de recursos gratuitos"
```

---

### Task 5: Política de protección de datos (mini-sitio)

**Files:**
- Create: `C:\Users\jcalu\Desktop\PROYECTOS CLAUDE\audit-ia-recursos\public\politica-datos\index.html`

- [ ] **Step 1: Crear la página** (misma identidad: navy `#0B1E36`, lime `#B7CE3B`, DM Sans; responsive):

```html
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Política de protección de datos | AuditConsulting Group</title>
<meta name="robots" content="noindex">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&display=swap" rel="stylesheet">
<style>
  :root { --navy:#0B1E36; --lime:#B7CE3B; --ink:#1f2937; --muted:#64748b; }
  * { box-sizing:border-box; }
  body { margin:0; font-family:"DM Sans",system-ui,-apple-system,"Segoe UI",sans-serif; color:var(--ink); background:#f5f7fa; line-height:1.6; }
  header { background:var(--navy); color:#fff; padding-block:28px; padding-inline:max(16px, calc((100% - 760px)/2)); }
  header a { color:var(--lime); text-decoration:none; font-size:14px; }
  h1 { margin:10px 0 0; font-size:clamp(22px,4vw,30px); }
  main { max-width:760px; margin:0 auto; padding:28px 16px 48px; }
  h2 { font-size:18px; color:var(--navy); margin:26px 0 6px; }
  .ver { color:var(--muted); font-size:13px; }
</style>
</head>
<body>
<header>
  <a href="../">← Recursos gratuitos</a>
  <h1>Política de protección de datos</h1>
</header>
<main>
  <p class="ver">Versión v1 · vigente desde el 14 de septiembre de 2026</p>

  <h2>Responsable</h2>
  <p>AuditConsulting Group (AuditConsulting Auditores Cía. Ltda.), Ecuador. Contacto: <a href="mailto:jcalupinia@auditconsulting.ec">jcalupinia@auditconsulting.ec</a> · WhatsApp 0990 609 811.</p>

  <h2>Datos que tratamos</h2>
  <p>Nombre, empresa y correo electrónico que usted ingresa al solicitar un recurso gratuito, la fecha en que aceptó esta política y datos técnicos mínimos de seguridad (dirección IP).</p>

  <h2>Finalidad</h2>
  <p>Darle acceso al recurso solicitado, enviarle a su correo el enlace de acceso y remitirle información de los servicios de la firma. No vendemos ni cedemos sus datos a terceros.</p>

  <h2>Base legal</h2>
  <p>Su consentimiento, conforme a la Ley Orgánica de Protección de Datos Personales del Ecuador (LOPDP). Puede retirarlo en cualquier momento.</p>

  <h2>Conservación</h2>
  <p>Conservamos sus datos mientras no solicite su eliminación.</p>

  <h2>Sus derechos</h2>
  <p>Puede ejercer sus derechos de acceso, rectificación, actualización, eliminación, oposición y portabilidad escribiendo a <a href="mailto:jcalupinia@auditconsulting.ec">jcalupinia@auditconsulting.ec</a>.</p>

  <h2>Encargados del tratamiento</h2>
  <p>Para operar este servicio usamos proveedores de alojamiento (Render) y de envío de correos (Resend), que tratan los datos solo por nuestra cuenta.</p>
</main>
</body>
</html>
```

- [ ] **Step 2: Verificar** — `python -m http.server 5500 --directory public` (vía `preview_start`, ver Tarea 8) y abrir `/politica-datos/`: se ve bien a 400 px y en escritorio, sin scroll horizontal.

- [ ] **Step 3: Commit (sin push)**

```bash
git -C "C:/Users/jcalu/Desktop/PROYECTOS CLAUDE/audit-ia-recursos" add public/politica-datos/index.html
git -C "C:/Users/jcalu/Desktop/PROYECTOS CLAUDE/audit-ia-recursos" commit -m "Política de protección de datos v1 (LOPDP)"
```

---

### Task 6: Recuadro de registro en la calculadora (mini-sitio)

**Files:**
- Modify: `audit-ia-recursos/public/anticipo-ir-2026/index.html` — insertar el bloque justo antes de `</body>` (hoy l.1442).

- [ ] **Step 1: Insertar el bloque** (antes de `</body>`):

```html
<!-- ===== Registro de acceso (recursos gratuitos) ===== -->
<style>
  body.gated > header, body.gated > main { filter:blur(3px); pointer-events:none; user-select:none; }
  #gate { position:fixed; inset:0; z-index:9999; display:grid; place-items:center; padding:16px; background:rgba(11,30,54,.72); font-family:"DM Sans",system-ui,-apple-system,"Segoe UI",sans-serif; }
  #gate .g-box { width:100%; max-width:440px; max-height:calc(100vh - 32px); overflow:auto; background:#fff; color:#1f2937; border-radius:14px; padding:26px 22px; box-shadow:0 20px 60px rgba(0,0,0,.35); }
  #gate h2 { margin:0 0 6px; color:#0B1E36; font-size:22px; line-height:1.25; }
  #gate p { margin:0 0 14px; font-size:14px; color:#475569; }
  #gate label { display:block; font-size:13px; font-weight:600; color:#0B1E36; margin:10px 0 4px; }
  #gate input[type=text], #gate input[type=email] { width:100%; box-sizing:border-box; padding:11px 12px; border:1px solid #cbd5e1; border-radius:8px; font:inherit; font-size:15px; }
  #gate input:focus { outline:2px solid #B7CE3B; border-color:#0B1E36; }
  #gate .g-check { display:flex; gap:8px; align-items:flex-start; font-weight:400; font-size:13px; color:#334155; margin-top:14px; }
  #gate .g-check input { margin-top:3px; }
  #gate .g-trampa { position:absolute; left:-9999px; width:1px; height:1px; overflow:hidden; }
  #gate button { width:100%; margin-top:16px; padding:13px; border:0; border-radius:8px; background:#0B1E36; color:#fff; font:inherit; font-weight:700; font-size:15px; cursor:pointer; }
  #gate button:disabled { opacity:.65; cursor:wait; }
  #gate .g-link { display:inline-block; margin-top:14px; background:none; border:0; padding:0; width:auto; color:#0B1E36; font-weight:600; font-size:13px; text-decoration:underline; cursor:pointer; }
  #gate .g-err { color:#b91c1c; font-size:13px; margin-top:10px; min-height:1em; }
  #gate a { color:#0B1E36; }
</style>
<div id="gate" hidden role="dialog" aria-modal="true" aria-labelledby="g-titulo">
  <div class="g-box">
    <form id="g-form" novalidate>
      <h2 id="g-titulo">Acceda gratis a la calculadora</h2>
      <p>Regístrese y le enviaremos el enlace de acceso a su correo. Su usuario es su correo.</p>
      <label for="g-nombre">Nombre</label>
      <input type="text" id="g-nombre" name="nombre" required minlength="3" maxlength="160" autocomplete="name">
      <label for="g-empresa">Empresa</label>
      <input type="text" id="g-empresa" name="empresa" required maxlength="200" autocomplete="organization">
      <label for="g-email">Correo</label>
      <input type="email" id="g-email" name="email" required maxlength="320" autocomplete="email">
      <div class="g-trampa" aria-hidden="true"><label for="g-web">Web</label><input type="text" id="g-web" name="website" tabindex="-1" autocomplete="off"></div>
      <label class="g-check"><input type="checkbox" name="acepta" required> <span>Acepto la <a href="../politica-datos/" target="_blank" rel="noopener">política de protección de datos</a> de AuditConsulting Group.</span></label>
      <button type="submit" id="g-enviar">Enviar</button>
      <div class="g-err" id="g-form-err" role="alert"></div>
      <button type="button" class="g-link" data-vista="g-reenvio">¿Ya se registró? Reenviar mi acceso</button>
    </form>
    <form id="g-reenvio" novalidate hidden>
      <h2>Reenviar mi acceso</h2>
      <p>Escriba el correo con el que se registró.</p>
      <label for="g-email2">Correo</label>
      <input type="email" id="g-email2" name="email" required maxlength="320" autocomplete="email">
      <button type="submit" id="g-reenviar">Reenviar enlace</button>
      <div class="g-err" id="g-reenvio-err" role="alert"></div>
      <button type="button" class="g-link" data-vista="g-form">← Volver al registro</button>
    </form>
    <div id="g-ok" hidden>
      <h2>Revise su correo</h2>
      <p id="g-ok-txt"></p>
      <button type="button" class="g-link" data-vista="g-reenvio">¿No le llegó? Reenviar</button>
    </div>
  </div>
</div>
<script>
(function () {
  var SLUG = "anticipo-ir-2026";
  var LOCAL = /^(localhost|127\.0\.0\.1)$/.test(location.hostname);
  var HOST = LOCAL ? "http://127.0.0.1:8000" : "https://auditbrain-python-runner.onrender.com";
  var API = HOST + "/api/v1/recursos/" + SLUG;
  var KEY = "acg_acceso_" + SLUG;
  var $ = function (id) { return document.getElementById(id); };

  function leer() { try { return localStorage.getItem(KEY); } catch (e) { return null; } }
  function guardar(v) { try { localStorage.setItem(KEY, v); } catch (e) {} }
  function vista(id) {
    ["g-form", "g-reenvio", "g-ok"].forEach(function (v) { $(v).hidden = v !== id; });
    var campo = $(id).querySelector("input:not([tabindex='-1'])");
    if (campo) campo.focus();
  }
  function abrir() { document.body.classList.remove("gated"); $("gate").hidden = true; }
  function cerrar(id) {
    document.body.classList.add("gated");
    $("gate").hidden = false;
    vista(id || "g-form");
    fetch(HOST + "/healthz", { mode: "no-cors" }).catch(function () {}); // despierta el servidor
  }
  function pedir(url, opts) {
    var ctl = new AbortController();
    var t = setTimeout(function () { ctl.abort(); }, 60000);
    opts = opts || {};
    opts.signal = ctl.signal;
    return fetch(url, opts).finally(function () { clearTimeout(t); });
  }
  function enviarJson(url, body) {
    return pedir(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    }).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (d) {
        if (r.ok) return d;
        if (r.status === 429) throw new Error("Demasiados intentos desde esta red. Intente en unos minutos.");
        if (r.status === 422) throw new Error("Revise los datos: nombre (mínimo 3 letras), empresa, un correo válido y la aceptación de la política.");
        throw new Error("No pudimos completar la solicitud. Intente de nuevo.");
      });
    }).catch(function (e) {
      if (e.name === "AbortError" || e instanceof TypeError) throw new Error("No pudimos conectar. Intente de nuevo.");
      throw e;
    });
  }
  function ocupado(btn, txt) {
    btn.disabled = true;
    btn.dataset.txt = btn.dataset.txt || btn.textContent;
    btn.textContent = txt;
    return setTimeout(function () { btn.textContent = "Conectando con el servidor…"; }, 4000);
  }
  function libre(btn, t) { clearTimeout(t); btn.disabled = false; btn.textContent = btn.dataset.txt; }

  Array.prototype.forEach.call(document.querySelectorAll("#gate [data-vista]"), function (b) {
    b.addEventListener("click", function () { vista(b.getAttribute("data-vista")); });
  });

  $("g-form").addEventListener("submit", function (e) {
    e.preventDefault();
    var f = e.target, err = $("g-form-err");
    err.textContent = "";
    if (!f.checkValidity()) {
      err.textContent = f.acepta.checked
        ? "Complete su nombre (mínimo 3 letras), su empresa y un correo válido."
        : "Para continuar debe aceptar la política de protección de datos.";
      return;
    }
    var body = {
      nombre: f.nombre.value.trim(),
      empresa: f.empresa.value.trim(),
      email: f.email.value.trim(),
      acepta_politica: f.acepta.checked,
      website: f.website.value
    };
    var btn = $("g-enviar"), t = ocupado(btn, "Enviando…");
    enviarJson(API + "/registros", body).then(function () {
      $("g-ok-txt").textContent = "Listo, " + body.nombre + ". Su usuario es su correo. Le enviamos el enlace de acceso a " + body.email + ". Revise también la bandeja de correo no deseado.";
      vista("g-ok");
    }).catch(function (x) { err.textContent = x.message; })
      .finally(function () { libre(btn, t); });
  });

  $("g-reenvio").addEventListener("submit", function (e) {
    e.preventDefault();
    var f = e.target, err = $("g-reenvio-err");
    err.textContent = "";
    if (!f.checkValidity()) { err.textContent = "Escriba un correo válido."; return; }
    var btn = $("g-reenviar"), t = ocupado(btn, "Enviando…");
    enviarJson(API + "/reenviar", { email: f.email.value.trim() }).then(function (d) {
      $("g-ok-txt").textContent = d.mensaje + " Revise también la bandeja de correo no deseado.";
      vista("g-ok");
    }).catch(function (x) { err.textContent = x.message; })
      .finally(function () { libre(btn, t); });
  });

  var token = new URLSearchParams(location.search).get("acceso");
  if (token) {
    history.replaceState(null, "", location.pathname + location.hash);
    cerrar("g-ok");
    $("g-ok-txt").textContent = "Verificando su acceso…";
    pedir(API + "/acceso?token=" + encodeURIComponent(token)).then(function (r) {
      if (!r.ok) throw new Error("invalido");
      guardar(token);
      abrir();
    }).catch(function () {
      vista("g-reenvio");
      $("g-reenvio-err").textContent = "Su enlace no es válido o venció. Solicite uno nuevo.";
    });
  } else if (leer()) {
    abrir();
  } else {
    cerrar("g-form");
  }
})();
</script>
<!-- ===== /Registro de acceso ===== -->
```

- [ ] **Step 2: Commit (sin push)**

```bash
git -C "C:/Users/jcalu/Desktop/PROYECTOS CLAUDE/audit-ia-recursos" add public/anticipo-ir-2026/index.html
git -C "C:/Users/jcalu/Desktop/PROYECTOS CLAUDE/audit-ia-recursos" commit -m "Calculadora Anticipo IR 2026: registro con acceso por correo"
```

---

### Task 7: Texto de la tarjeta en el índice (mini-sitio)

**Files:**
- Modify: `audit-ia-recursos/public/index.html:305` (tarjeta `href="anticipo-ir-2026/"`)

- [ ] **Step 1:** reemplazar `<span class="go">Abrir calculadora` por `<span class="go">Quiero la calculadora gratis` (se conserva el `<svg>` que sigue).

- [ ] **Step 2: Commit (sin push)**

```bash
git -C "C:/Users/jcalu/Desktop/PROYECTOS CLAUDE/audit-ia-recursos" add public/index.html
git -C "C:/Users/jcalu/Desktop/PROYECTOS CLAUDE/audit-ia-recursos" commit -m "Tarjeta: Quiero la calculadora gratis"
```

---

### Task 8: Verificación de punta a punta en local

**Files:**
- Create: `C:\Users\jcalu\Desktop\PROYECTOS CLAUDE\ab-recursos-leads\.claude\launch.json` (no se commitea; está fuera del alcance del PR)

- [ ] **Step 1: launch.json** con dos servidores:

```json
{
  "version": "0.0.1",
  "configurations": [
    {
      "name": "api-local",
      "runtimeExecutable": "python",
      "runtimeArgs": ["-m", "uvicorn", "app:app", "--port", "8000"],
      "env": {
        "DATABASE_URL": "sqlite:///./e2e_recursos.db",
        "CORS_ALLOW_ORIGINS": "http://127.0.0.1:5500,http://localhost:5500"
      },
      "port": 8000
    },
    {
      "name": "recursos-local",
      "runtimeExecutable": "python",
      "runtimeArgs": ["-m", "http.server", "5500", "--bind", "127.0.0.1", "--directory", "C:/Users/jcalu/Desktop/PROYECTOS CLAUDE/audit-ia-recursos/public"],
      "port": 5500
    }
  ]
}
```

Si `env` no se aplica, crear `e2e_api.cmd` con `set DATABASE_URL=…` / `set CORS_ALLOW_ORIGINS=…` / `python -m uvicorn app:app --port 8000` y usarlo como `runtimeExecutable`.

- [ ] **Step 2: Levantar** — `preview_start {name:"api-local"}` y `preview_start {name:"recursos-local"}`. Abrir `http://127.0.0.1:5500/anticipo-ir-2026/`.

- [ ] **Step 3: Recuadro visible** — `read_page`: existe el diálogo "Acceda gratis a la calculadora"; el `<main>` tiene blur (`getComputedStyle(document.querySelector('main')).filter` contiene `blur`).

- [ ] **Step 4: Validaciones** — Enviar vacío → mensaje de error; sin marcar la casilla → "debe aceptar la política".

- [ ] **Step 5: Registro** — llenar nombre "Prueba E2E", empresa "Alfa S.A.", correo `e2e@example.com`, marcar, Enviar → vista "Revise su correo" con el correo. `read_network_requests`: `POST …/registros` = 201. En el log del backend: el intento de correo (sin `RESEND_API_KEY` falla y deja `email_enviado=false`; es lo esperado en local).

- [ ] **Step 6: Enlace** — generar el token del lead 1 con la misma base:

```bash
DATABASE_URL=sqlite:///./e2e_recursos.db python -c "from backend.app.recursos.tokens import crear_token; print(crear_token(1,'anticipo-ir-2026'))"
```

Navegar a `http://127.0.0.1:5500/anticipo-ir-2026/?acceso=<token>` → el recuadro desaparece, la URL queda sin `?acceso=`, `localStorage["acg_acceso_anticipo-ir-2026"]` existe. Recargar → entra directo. Probar "Procesar Cálculo" con el ejemplo (Alfa S.A.) → la calculadora funciona.

- [ ] **Step 7: Enlace inválido** — borrar `localStorage`, navegar con `?acceso=basura` → vista "Reenviar mi acceso" con "Su enlace no es válido o venció".

- [ ] **Step 8: Consola** — `GET http://127.0.0.1:8000/api/v1/recursos/registros` con token de admin local (crear con el patrón de `docs`/memoria "Correr AUDIT-IA local para E2E") → el registro aparece con `verificado_at` lleno. Levantar la consola Vite (`VITE_PROXY_TARGET=http://127.0.0.1:8000`) y ver la pestaña REC con la fila ✅.

- [ ] **Step 9: Móvil** — `resize_window {preset:"mobile"}` → recuadro legible, sin scroll horizontal; volver a `desktop`. Captura de pantalla como evidencia.

- [ ] **Step 10:** detener los servidores (`preview_stop`), borrar `e2e_recursos.db`.

---

### Task 9: PR, configuración y despliegue

- [ ] **Step 1: PR del portal**

```bash
git push -u origin feat/recursos-leads
gh pr create --title "Recursos gratuitos: registro con acceso por correo (calculadora Anticipo IR 2026)" --body "<resumen + checklist de pruebas + tareas en Render>"
```

- [ ] **Step 2: Usuario (Render, requiere su cuenta):**
  1. Servicio `auditbrain-python-runner` → Environment → `CORS_ALLOW_ORIGINS`: agregar `,https://recursos.audit-ia.ec`.
  2. Confirmar `RESEND_API_KEY` cargada y el dominio `auditconsulting.ec` verificado en Resend.
- [ ] **Step 3:** merge del PR (lo decide el usuario) → esperar el deploy → `curl -s -o /dev/null -w "%{http_code}" -X POST https://auditbrain-python-runner.onrender.com/api/v1/recursos/anticipo-ir-2026/reenviar -H "Content-Type: application/json" -d "{\"email\":\"x@example.com\"}"` → `200`. Preflight CORS: `curl -s -D - -o /dev/null -X OPTIONS -H "Origin: https://recursos.audit-ia.ec" -H "Access-Control-Request-Method: POST" …/registros` → cabecera `access-control-allow-origin: https://recursos.audit-ia.ec`.
- [ ] **Step 4:** con la confirmación del usuario, `git push` del mini-sitio → Render publica. Registrar un correo real del usuario en `https://recursos.audit-ia.ec/anticipo-ir-2026/`, confirmar que llega el correo, abrir el enlace y verlo en la pestaña REC como verificado.
- [ ] **Step 5:** actualizar la memoria (`video-auditoria-2026-heygen-pipeline.md`: el formulario ya existe; `mini-sitio-recursos-render.md`: recuadro de registro + `politica-datos/`).
