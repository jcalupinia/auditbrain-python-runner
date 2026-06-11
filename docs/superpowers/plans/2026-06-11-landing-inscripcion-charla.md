# Landing de Inscripción a la Charla — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir una landing pública de inscripción a la charla de Audit Consulting Group dentro del portal de clientes (`frontend-client`), que persiste cada inscripción en Postgres y dispara confirmación automática por email (Resend) y WhatsApp (Cloud API), más un aviso interno a la firma.

**Architecture:** Backend FastAPI nuevo módulo `backend/app/events/` (modelo + schemas + servicio + router público/admin) que reutiliza la infra existente de `notifications/email.py` (Resend), `client_portal/rate_limit.py` y el patrón `BackgroundTasks`. Un módulo nuevo `notifications/whatsapp.py` (Cloud API con degradación elegante). Frontend: ruta pública nueva `/charla` en `frontend-client` (React + react-router-dom) con landing calcada del flyer + formulario.

**Tech Stack:** Python 3.13, FastAPI 0.115, SQLAlchemy 2.0, Pydantic 2.8.2, pytest, React 18, react-router-dom 6, Vite 5.

**Idioma:** toda comunicación con el usuario en español (regla CLAUDE.md). Código y comentarios siguen la convención del repo.

> **Nota sobre commits:** los pasos incluyen `git commit` (metodología TDD del repo). Confirmar con el usuario antes del primer commit y crear branch si se está en la rama por defecto (política del entorno: commitear solo cuando el usuario lo pide).

---

## File Structure

**Backend (crear):**
- `backend/app/events/__init__.py` — paquete vacío.
- `backend/app/events/catalog.py` — `EventInfo` (dataclass) + dict `EVENTS` + `get_event(slug)`.
- `backend/app/events/models.py` — modelo SQLAlchemy `EventRegistration`.
- `backend/app/events/schemas.py` — Pydantic: `RegistrationCreate`, `RegistrationResponse`, `RegistrationOut`.
- `backend/app/events/service.py` — `create_registration`, `list_registrations`.
- `backend/app/events/notify.py` — `process_registration_notifications(registration_id)`.
- `backend/app/events/router.py` — endpoints POST (público) y GET (admin).
- `backend/app/notifications/whatsapp.py` — WhatsApp Cloud API.
- `backend/app/notifications/templates/charla_confirmacion.html` — email al inscrito.
- `backend/app/notifications/templates/charla_aviso_interno.html` — email a la firma.

**Backend (modificar):**
- `backend/app/notifications/email.py` — helpers `render/send_charla_confirmacion` y `render/send_charla_aviso_interno`.
- `backend/app/api/__init__.py` — montar `events_router`.
- `backend/app/db/session.py` — `init_db()` importa `events.models`.

**Frontend (crear):**
- `frontend-client/src/charla/CharlaLanding.jsx` — página landing + estado de éxito.
- `frontend-client/src/charla/CharlaForm.jsx` — formulario controlado + validación cliente.
- `frontend-client/src/charla/charla.css` — estilos específicos.

**Frontend (modificar):**
- `frontend-client/src/api.js` — export `registrarCharla(slug, payload)`.
- `frontend-client/src/App.jsx` — ruta `<Route path="/charla">`.

**Tests (crear):**
- `tests/test_events_catalog.py`
- `tests/test_events_schemas.py`
- `tests/test_events_service.py`
- `tests/test_notifications_whatsapp.py`
- `tests/test_notifications_charla_email.py`
- `tests/test_events_notify.py`
- `tests/test_events_router.py`

---

## Task 1: Catálogo del evento

**Files:**
- Create: `backend/app/events/__init__.py`
- Create: `backend/app/events/catalog.py`
- Test: `tests/test_events_catalog.py`

- [ ] **Step 1: Crear el paquete**

Create `backend/app/events/__init__.py` con contenido vacío (un comentario):

```python
"""Módulo de eventos / inscripciones (charlas, webinars)."""
```

- [ ] **Step 2: Escribir el test que falla**

Create `tests/test_events_catalog.py`:

```python
from backend.app.events.catalog import EVENTS, get_event


def test_charla_event_exists():
    ev = get_event("charla-anexos-2026-06")
    assert ev is not None
    assert ev.titulo == "Elaboración de Anexos Tributarios con Herramienta de Automatización"
    assert ev.fecha_texto == "Jueves 18 de junio"
    assert ev.modalidad == "Zoom"
    assert len(ev.beneficios) == 5
    assert ev.activo is True


def test_get_event_unknown_returns_none():
    assert get_event("no-existe") is None


def test_events_dict_keyed_by_slug():
    for slug, ev in EVENTS.items():
        assert ev.slug == slug
```

- [ ] **Step 3: Correr el test para verificar que falla**

Run: `python -m pytest tests/test_events_catalog.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'backend.app.events.catalog'`

- [ ] **Step 4: Implementar el catálogo**

Create `backend/app/events/catalog.py`:

```python
"""Catálogo de eventos. Un evento por slug; configurable sin rediseño."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class EventInfo:
    slug: str
    titulo: str
    subtitulo: str
    fecha_texto: str
    hora_texto: str
    duracion_texto: str
    modalidad: str
    zoom_url: str
    beneficios: list[str] = field(default_factory=list)
    activo: bool = True


def _build_events() -> dict[str, EventInfo]:
    charla = EventInfo(
        slug="charla-anexos-2026-06",
        titulo="Elaboración de Anexos Tributarios con Herramienta de Automatización",
        subtitulo="Charla gratuita en Zoom",
        fecha_texto="Jueves 18 de junio",
        hora_texto="19h00 (Ecuador)",
        duracion_texto="2 horas",
        modalidad="Zoom",
        zoom_url=os.getenv("CHARLA_ZOOM_URL", ""),
        beneficios=[
            "Automatiza tus anexos tributarios",
            "Descarga inteligente de información del SRI",
            "Validaciones automáticas y control de inconsistencias",
            "Reduce tiempos y minimiza errores",
            "Casos prácticos para empresas y profesionales",
        ],
        activo=True,
    )
    return {charla.slug: charla}


EVENTS: dict[str, EventInfo] = _build_events()


def get_event(slug: str) -> EventInfo | None:
    return EVENTS.get(slug)
```

- [ ] **Step 5: Correr el test para verificar que pasa**

Run: `python -m pytest tests/test_events_catalog.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: Commit**

```bash
git add backend/app/events/__init__.py backend/app/events/catalog.py tests/test_events_catalog.py
git commit -m "feat(events): catálogo del evento charla de anexos tributarios"
```

---

## Task 2: Modelo EventRegistration

**Files:**
- Create: `backend/app/events/models.py`
- Modify: `backend/app/db/session.py` (función `init_db`)
- Test: `tests/test_events_models.py`

- [ ] **Step 1: Escribir el test que falla**

Create `tests/test_events_models.py`:

```python
import uuid

import pytest

from backend.app.db.session import SessionLocal, init_db
from backend.app.events.models import EventRegistration


@pytest.fixture(autouse=True)
def _db():
    init_db()
    yield


def test_can_insert_registration():
    db = SessionLocal()
    try:
        reg = EventRegistration(
            event_slug="charla-anexos-2026-06",
            nombre="María Pérez",
            email=f"maria-{uuid.uuid4().hex[:8]}@example.com",
            telefono_e164="+593987654321",
            documento="1791240154001",
            empresa="Empresa S.A.",
        )
        db.add(reg)
        db.commit()
        db.refresh(reg)
        assert reg.id is not None
        assert reg.estado == "registrado"
        assert reg.email_enviado is False
        assert reg.whatsapp_enviado is False
        assert reg.aviso_interno_enviado is False
        assert reg.created_at is not None
    finally:
        db.close()
```

- [ ] **Step 2: Correr el test para verificar que falla**

Run: `python -m pytest tests/test_events_models.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'backend.app.events.models'`

- [ ] **Step 3: Implementar el modelo**

Create `backend/app/events/models.py`:

```python
"""Modelo de inscripción a eventos."""

import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.session import Base


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


class EventRegistration(Base):
    __tablename__ = "event_registrations"
    __table_args__ = (
        UniqueConstraint("event_slug", "email", name="uq_event_registration_slug_email"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_slug: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str] = mapped_column(String(320), index=True, nullable=False)
    telefono_e164: Mapped[str] = mapped_column(String(20), nullable=False)
    documento: Mapped[str] = mapped_column(String(20), nullable=False)
    empresa: Mapped[str] = mapped_column(String(200), nullable=False)
    estado: Mapped[str] = mapped_column(String(16), default="registrado", nullable=False)
    email_enviado: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    whatsapp_enviado: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    aviso_interno_enviado: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False
    )
```

- [ ] **Step 4: Registrar el modelo en `init_db`**

In `backend/app/db/session.py`, dentro de `init_db()`, añadir el import junto a los otros imports de modelos (después de la línea `from backend.app.ict import models as _ict_models  # noqa: F401`):

```python
    from backend.app.events import models as _events_models  # noqa: F401
```

- [ ] **Step 5: Correr el test para verificar que pasa**

Run: `python -m pytest tests/test_events_models.py -v`
Expected: PASS (1 passed)

- [ ] **Step 6: Commit**

```bash
git add backend/app/events/models.py backend/app/db/session.py tests/test_events_models.py
git commit -m "feat(events): modelo EventRegistration + registro en init_db"
```

---

## Task 3: Schemas Pydantic (validación + normalización de teléfono)

**Files:**
- Create: `backend/app/events/schemas.py`
- Test: `tests/test_events_schemas.py`

- [ ] **Step 1: Escribir el test que falla**

Create `tests/test_events_schemas.py`:

```python
import pytest
from pydantic import ValidationError

from backend.app.events.schemas import RegistrationCreate


def _valid(**over):
    base = dict(
        nombre="María Pérez",
        email="maria@empresa.ec",
        telefono="0987654321",
        telefono_pais="+593",
        documento="1791240154001",
        empresa="Empresa S.A.",
    )
    base.update(over)
    return RegistrationCreate(**base)


def test_phone_normalized_to_e164_strips_leading_zero():
    m = _valid()
    assert m.telefono_e164 == "+593987654321"


def test_phone_accepts_spaces_and_dashes():
    m = _valid(telefono="098-765 4321")
    assert m.telefono_e164 == "+593987654321"


def test_documento_cedula_10_ok():
    m = _valid(documento="1712345678")
    assert m.documento == "1712345678"


def test_documento_invalid_length_rejected():
    with pytest.raises(ValidationError):
        _valid(documento="12345")


def test_email_invalid_rejected():
    with pytest.raises(ValidationError):
        _valid(email="no-es-email")


def test_nombre_too_short_rejected():
    with pytest.raises(ValidationError):
        _valid(nombre="A")
```

- [ ] **Step 2: Correr el test para verificar que falla**

Run: `python -m pytest tests/test_events_schemas.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'backend.app.events.schemas'`

- [ ] **Step 3: Implementar los schemas**

Create `backend/app/events/schemas.py`:

```python
"""Schemas Pydantic del módulo de eventos."""

from __future__ import annotations

import datetime
import re

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

_E164 = re.compile(r"^\+\d{8,15}$")
_PAIS = re.compile(r"^\+\d{1,4}$")


class RegistrationCreate(BaseModel):
    nombre: str = Field(min_length=3, max_length=160)
    email: EmailStr
    telefono: str = Field(min_length=6, max_length=20)
    telefono_pais: str = Field(default="+593", max_length=5)
    documento: str = Field(min_length=8, max_length=20)
    empresa: str = Field(min_length=1, max_length=200)
    # Calculado en el validador a partir de telefono + telefono_pais.
    telefono_e164: str = ""

    @field_validator("documento")
    @classmethod
    def _validate_documento(cls, v: str) -> str:
        digits = re.sub(r"\D", "", v)
        if len(digits) not in (10, 13):
            raise ValueError("La cédula debe tener 10 dígitos o el RUC 13 dígitos.")
        return digits

    @field_validator("telefono_pais")
    @classmethod
    def _validate_pais(cls, v: str) -> str:
        v = v.strip()
        if not _PAIS.match(v):
            raise ValueError("Código de país inválido (ej. +593).")
        return v

    @model_validator(mode="after")
    def _normalize_phone(self) -> "RegistrationCreate":
        local = re.sub(r"\D", "", self.telefono).lstrip("0")
        pais = self.telefono_pais.lstrip("+")
        e164 = f"+{pais}{local}"
        if not _E164.match(e164):
            raise ValueError("Número de teléfono inválido.")
        object.__setattr__(self, "telefono_e164", e164)
        return self


class RegistrationResponse(BaseModel):
    ok: bool
    estado: str
    ya_inscrito: bool
    mensaje: str


class RegistrationOut(BaseModel):
    id: int
    event_slug: str
    nombre: str
    email: str
    telefono_e164: str
    documento: str
    empresa: str
    estado: str
    email_enviado: bool
    whatsapp_enviado: bool
    aviso_interno_enviado: bool
    created_at: datetime.datetime

    model_config = {"from_attributes": True}
```

> Nota: `RegistrationCreate` NO es frozen, por eso `object.__setattr__` no es estrictamente necesario, pero es robusto si en el futuro se congela el modelo.

- [ ] **Step 4: Correr el test para verificar que pasa**

Run: `python -m pytest tests/test_events_schemas.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Verificar que `email-validator` está instalado (EmailStr)**

Run: `python -c "import email_validator; print('ok')"`
Expected: imprime `ok`. Si falla con `ModuleNotFoundError`, añadir a `requirements.txt` la línea `email-validator==2.2.0` (debajo de `pydantic==2.8.2`) e instalar con `pip install email-validator==2.2.0`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/events/schemas.py tests/test_events_schemas.py
git commit -m "feat(events): schemas con validación y normalización E.164"
```

---

## Task 4: Servicio (creación idempotente + listado)

**Files:**
- Create: `backend/app/events/service.py`
- Test: `tests/test_events_service.py`

- [ ] **Step 1: Escribir el test que falla**

Create `tests/test_events_service.py`:

```python
import uuid

import pytest

from backend.app.db.session import SessionLocal, init_db
from backend.app.events import service
from backend.app.events.schemas import RegistrationCreate


@pytest.fixture(autouse=True)
def _db():
    init_db()
    yield


def _payload(email):
    return RegistrationCreate(
        nombre="María Pérez",
        email=email,
        telefono="0987654321",
        telefono_pais="+593",
        documento="1791240154001",
        empresa="Empresa S.A.",
    )


def test_create_registration_persists_and_returns_false():
    db = SessionLocal()
    try:
        email = f"a-{uuid.uuid4().hex[:8]}@example.com"
        reg, ya = service.create_registration(
            db, event_slug="charla-anexos-2026-06", data=_payload(email)
        )
        assert ya is False
        assert reg.id is not None
        assert reg.email == email.lower()
        assert reg.telefono_e164 == "+593987654321"
    finally:
        db.close()


def test_create_registration_idempotent_same_email():
    db = SessionLocal()
    try:
        email = f"b-{uuid.uuid4().hex[:8]}@example.com"
        reg1, ya1 = service.create_registration(
            db, event_slug="charla-anexos-2026-06", data=_payload(email)
        )
        reg2, ya2 = service.create_registration(
            db, event_slug="charla-anexos-2026-06", data=_payload(email)
        )
        assert ya1 is False
        assert ya2 is True
        assert reg1.id == reg2.id
    finally:
        db.close()


def test_list_registrations_returns_desc():
    db = SessionLocal()
    try:
        slug = f"evt-{uuid.uuid4().hex[:6]}"
        for i in range(3):
            service.create_registration(
                db, event_slug=slug, data=_payload(f"c{i}-{uuid.uuid4().hex[:6]}@x.com")
            )
        rows = service.list_registrations(db, event_slug=slug, limit=10)
        assert len(rows) == 3
    finally:
        db.close()
```

- [ ] **Step 2: Correr el test para verificar que falla**

Run: `python -m pytest tests/test_events_service.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'backend.app.events.service'`

- [ ] **Step 3: Implementar el servicio**

Create `backend/app/events/service.py`:

```python
"""Lógica de negocio de inscripciones."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.events.models import EventRegistration
from backend.app.events.schemas import RegistrationCreate


def _find(db: Session, event_slug: str, email: str) -> EventRegistration | None:
    return db.execute(
        select(EventRegistration).where(
            EventRegistration.event_slug == event_slug,
            EventRegistration.email == email,
        )
    ).scalar_one_or_none()


def create_registration(
    db: Session, *, event_slug: str, data: RegistrationCreate
) -> tuple[EventRegistration, bool]:
    """Crea (o reusa) una inscripción. Devuelve (registro, ya_inscrito)."""
    email = data.email.lower()
    existing = _find(db, event_slug, email)
    if existing is not None:
        return existing, True

    reg = EventRegistration(
        event_slug=event_slug,
        nombre=data.nombre.strip(),
        email=email,
        telefono_e164=data.telefono_e164,
        documento=data.documento,
        empresa=data.empresa.strip(),
    )
    db.add(reg)
    try:
        db.commit()
    except IntegrityError:
        # Carrera: otra request insertó el mismo (slug,email) en paralelo.
        db.rollback()
        existing = _find(db, event_slug, email)
        if existing is not None:
            return existing, True
        raise
    db.refresh(reg)
    return reg, False


def list_registrations(
    db: Session, *, event_slug: str, limit: int = 100
) -> list[EventRegistration]:
    return list(
        db.execute(
            select(EventRegistration)
            .where(EventRegistration.event_slug == event_slug)
            .order_by(EventRegistration.created_at.desc(), EventRegistration.id.desc())
            .limit(limit)
        ).scalars()
    )
```

- [ ] **Step 4: Correr el test para verificar que pasa**

Run: `python -m pytest tests/test_events_service.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/events/service.py tests/test_events_service.py
git commit -m "feat(events): servicio de inscripción idempotente + listado"
```

---

## Task 5: WhatsApp Cloud API (degradación elegante)

**Files:**
- Create: `backend/app/notifications/whatsapp.py`
- Test: `tests/test_notifications_whatsapp.py`

- [ ] **Step 1: Escribir el test que falla**

Create `tests/test_notifications_whatsapp.py`:

```python
from backend.app.notifications import whatsapp as wa


def test_no_config_returns_none(monkeypatch):
    for var in ("WHATSAPP_TOKEN", "WHATSAPP_PHONE_NUMBER_ID", "WHATSAPP_TEMPLATE_NAME"):
        monkeypatch.delenv(var, raising=False)
    result = wa.send_template_message(to_e164="+593987654321", variables=["María"])
    assert result is None


def test_builds_template_body(monkeypatch):
    monkeypatch.setenv("WHATSAPP_TOKEN", "tok")
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "12345")
    monkeypatch.setenv("WHATSAPP_TEMPLATE_NAME", "confirmacion_charla")
    monkeypatch.setenv("WHATSAPP_TEMPLATE_LANG", "es")

    captured = {}

    class _Resp:
        status_code = 200

        def json(self):
            return {"messages": [{"id": "wamid.x"}]}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return _Resp()

    monkeypatch.setattr(wa.requests, "post", fake_post)

    result = wa.send_template_message(
        to_e164="+593987654321", variables=["María", "Jueves 18 de junio", "19h00"]
    )
    assert result == {"messages": [{"id": "wamid.x"}]}
    assert "12345/messages" in captured["url"]
    assert captured["json"]["to"] == "593987654321"
    assert captured["json"]["type"] == "template"
    assert captured["json"]["template"]["name"] == "confirmacion_charla"
    params = captured["json"]["template"]["components"][0]["parameters"]
    assert [p["text"] for p in params] == ["María", "Jueves 18 de junio", "19h00"]
```

- [ ] **Step 2: Correr el test para verificar que falla**

Run: `python -m pytest tests/test_notifications_whatsapp.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'backend.app.notifications.whatsapp'`

- [ ] **Step 3: Implementar el módulo WhatsApp**

Create `backend/app/notifications/whatsapp.py`:

```python
"""WhatsApp Cloud API (Meta) con degradación elegante + retry.

El lead nunca inicia la conversación (llena un formulario web), por lo que
NO existe ventana de servicio de 24h: el primer mensaje proactivo DEBE ser
una plantilla pre-aprobada por Meta (categoría utility).

Si faltan las env vars, NO se rompe el flujo: se loguea y se retorna None.
"""

from __future__ import annotations

import logging
import os
import time

import requests

log = logging.getLogger(__name__)

_GRAPH_VERSION = "v21.0"


def _config() -> tuple[str, str, str, str]:
    return (
        os.getenv("WHATSAPP_TOKEN", "").strip(),
        os.getenv("WHATSAPP_PHONE_NUMBER_ID", "").strip(),
        os.getenv("WHATSAPP_TEMPLATE_NAME", "").strip(),
        os.getenv("WHATSAPP_TEMPLATE_LANG", "es").strip() or "es",
    )


def send_template_message(
    *, to_e164: str, variables: list[str], max_retries: int = 3
) -> dict | None:
    token, phone_id, template, lang = _config()
    if not (token and phone_id and template):
        log.warning(
            "WhatsApp no configurado (faltan env vars). Mensaje a %s omitido.", to_e164
        )
        return None

    url = f"https://graph.facebook.com/{_GRAPH_VERSION}/{phone_id}/messages"
    body = {
        "messaging_product": "whatsapp",
        "to": to_e164.lstrip("+"),
        "type": "template",
        "template": {
            "name": template,
            "language": {"code": lang},
            "components": [
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": v} for v in variables],
                }
            ],
        },
    }

    delay = 1.0
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=15,
            )
            if resp.status_code >= 400:
                raise RuntimeError(f"WhatsApp {resp.status_code}: {resp.text[:200]}")
            return resp.json()
        except Exception as e:  # noqa: BLE001
            log.warning(
                "send_template_message attempt %d/%d failed: %s", attempt, max_retries, e
            )
            if attempt < max_retries:
                time.sleep(delay)
                delay *= 2
    log.error(
        "send_template_message FAILED after %d retries to=%s", max_retries, to_e164
    )
    return None
```

- [ ] **Step 4: Correr el test para verificar que pasa**

Run: `python -m pytest tests/test_notifications_whatsapp.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/notifications/whatsapp.py tests/test_notifications_whatsapp.py
git commit -m "feat(notifications): WhatsApp Cloud API con degradación elegante"
```

---

## Task 6: Emails de la charla (plantillas + helpers)

**Files:**
- Create: `backend/app/notifications/templates/charla_confirmacion.html`
- Create: `backend/app/notifications/templates/charla_aviso_interno.html`
- Modify: `backend/app/notifications/email.py`
- Test: `tests/test_notifications_charla_email.py`

- [ ] **Step 1: Escribir el test que falla**

Create `tests/test_notifications_charla_email.py`:

```python
from backend.app.notifications import email as email_mod


def test_render_confirmacion_substitutes_vars():
    html = email_mod.render_charla_confirmacion(
        nombre="María",
        titulo="Elaboración de Anexos Tributarios con Herramienta de Automatización",
        fecha="Jueves 18 de junio",
        hora="19h00 (Ecuador)",
        modalidad="Zoom",
        zoom_url="https://zoom.us/j/123",
    )
    assert "María" in html
    assert "Jueves 18 de junio" in html
    assert "https://zoom.us/j/123" in html
    assert "{{" not in html  # no quedan placeholders sin reemplazar


def test_render_confirmacion_without_zoom_url_no_button():
    html = email_mod.render_charla_confirmacion(
        nombre="María", titulo="T", fecha="F", hora="H", modalidad="Zoom", zoom_url=""
    )
    assert "{{" not in html
    assert "Unirme por Zoom" not in html


def test_send_confirmacion_calls_send_email(monkeypatch):
    captured = {}

    def fake_send_email(*, to, subject, html, max_retries=3):
        captured["to"] = to
        captured["subject"] = subject
        return {"id": "email_x"}

    monkeypatch.setattr(email_mod, "send_email", fake_send_email)
    out = email_mod.send_charla_confirmacion(
        to="maria@x.com", nombre="María", titulo="T",
        fecha="F", hora="H", modalidad="Zoom", zoom_url="",
    )
    assert out == {"id": "email_x"}
    assert captured["to"] == "maria@x.com"
    assert "T" in captured["subject"]


def test_send_aviso_interno_uses_env_recipient(monkeypatch):
    monkeypatch.setenv("EVENTS_NOTIFY_EMAIL", "firma@auditconsulting.ec")
    captured = {}

    def fake_send_email(*, to, subject, html, max_retries=3):
        captured["to"] = to
        return {"id": "x"}

    monkeypatch.setattr(email_mod, "send_email", fake_send_email)
    email_mod.send_charla_aviso_interno(
        nombre="María", email="maria@x.com", telefono="+593987654321",
        documento="1791240154001", empresa="Empresa S.A.", titulo="T",
    )
    assert captured["to"] == "firma@auditconsulting.ec"
```

- [ ] **Step 2: Correr el test para verificar que falla**

Run: `python -m pytest tests/test_notifications_charla_email.py -v`
Expected: FAIL con `AttributeError: module ... has no attribute 'render_charla_confirmacion'`

- [ ] **Step 3: Crear la plantilla de confirmación**

Create `backend/app/notifications/templates/charla_confirmacion.html`:

```html
<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:0;background:#f4f6f8">
  <div style="background:#0a2540;padding:24px;text-align:center">
    <h2 style="color:#fff;margin:0">Audit Consulting Group</h2>
    <p style="margin:6px 0 0;color:#9fb3c8;font-size:13px">Powered by Audit-IA</p>
  </div>
  <div style="padding:24px">
    <p>Hola {{nombre}},</p>
    <p>Tu reserva quedó <strong>confirmada</strong>. Te esperamos en:</p>
    <h3 style="color:#0a2540;margin:8px 0">{{titulo}}</h3>
    <table style="width:100%;border-collapse:collapse;margin:16px 0;font-size:15px">
      <tr><td style="padding:6px 0;color:#64748b">Fecha</td><td style="padding:6px 0"><strong>{{fecha}}</strong></td></tr>
      <tr><td style="padding:6px 0;color:#64748b">Hora</td><td style="padding:6px 0"><strong>{{hora}}</strong></td></tr>
      <tr><td style="padding:6px 0;color:#64748b">Modalidad</td><td style="padding:6px 0"><strong>{{modalidad}}</strong></td></tr>
    </table>
    {{zoom_block}}
    <p style="color:#64748b;font-size:13px;border-top:1px solid #e2e8f0;padding-top:14px;margin-top:24px">
      Si no esperabas este mensaje, ignóralo. Mensaje automático de Audit Consulting Group.
    </p>
  </div>
</body>
</html>
```

- [ ] **Step 4: Crear la plantilla de aviso interno**

Create `backend/app/notifications/templates/charla_aviso_interno.html`:

```html
<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px">
  <h2 style="color:#0a2540;margin:0 0 4px">Nueva inscripción</h2>
  <p style="color:#64748b;margin:0 0 16px">{{titulo}}</p>
  <table style="width:100%;border-collapse:collapse;font-size:14px">
    <tr><td style="padding:6px 0;color:#64748b;width:140px">Nombre</td><td style="padding:6px 0"><strong>{{nombre}}</strong></td></tr>
    <tr><td style="padding:6px 0;color:#64748b">Email</td><td style="padding:6px 0">{{email}}</td></tr>
    <tr><td style="padding:6px 0;color:#64748b">WhatsApp</td><td style="padding:6px 0">{{telefono}}</td></tr>
    <tr><td style="padding:6px 0;color:#64748b">Cédula/RUC</td><td style="padding:6px 0">{{documento}}</td></tr>
    <tr><td style="padding:6px 0;color:#64748b">Empresa</td><td style="padding:6px 0">{{empresa}}</td></tr>
  </table>
</body>
</html>
```

- [ ] **Step 5: Añadir helpers a `email.py`**

In `backend/app/notifications/email.py`, añadir al final del archivo (usa `html` y `os`, ya importado `os`; añadir `import html` al inicio junto a los otros imports):

Primero, añadir el import al inicio (después de `import os`):

```python
import html as _html
```

Luego, al final del archivo:

```python
def render_charla_confirmacion(
    *, nombre: str, titulo: str, fecha: str, hora: str, modalidad: str, zoom_url: str
) -> str:
    tpl = (_TEMPLATES_DIR / "charla_confirmacion.html").read_text(encoding="utf-8")
    if zoom_url:
        zoom_block = (
            '<p style="text-align:center;margin:24px 0">'
            f'<a href="{_html.escape(zoom_url, quote=True)}" '
            'style="background:#8bc34a;color:#0a2540;font-weight:bold;padding:12px 28px;'
            'text-decoration:none;border-radius:6px;display:inline-block">Unirme por Zoom</a></p>'
        )
    else:
        zoom_block = ""
    return (
        tpl.replace("{{nombre}}", _html.escape(nombre))
        .replace("{{titulo}}", _html.escape(titulo))
        .replace("{{fecha}}", _html.escape(fecha))
        .replace("{{hora}}", _html.escape(hora))
        .replace("{{modalidad}}", _html.escape(modalidad))
        .replace("{{zoom_block}}", zoom_block)
    )


def send_charla_confirmacion(
    *, to: str, nombre: str, titulo: str, fecha: str, hora: str, modalidad: str, zoom_url: str
) -> dict | None:
    html_body = render_charla_confirmacion(
        nombre=nombre, titulo=titulo, fecha=fecha, hora=hora, modalidad=modalidad, zoom_url=zoom_url
    )
    return send_email(
        to=to, subject=f"Confirmación de tu reserva — {titulo}", html=html_body
    )


def render_charla_aviso_interno(
    *, nombre: str, email: str, telefono: str, documento: str, empresa: str, titulo: str
) -> str:
    tpl = (_TEMPLATES_DIR / "charla_aviso_interno.html").read_text(encoding="utf-8")
    return (
        tpl.replace("{{nombre}}", _html.escape(nombre))
        .replace("{{email}}", _html.escape(email))
        .replace("{{telefono}}", _html.escape(telefono))
        .replace("{{documento}}", _html.escape(documento))
        .replace("{{empresa}}", _html.escape(empresa))
        .replace("{{titulo}}", _html.escape(titulo))
    )


def send_charla_aviso_interno(
    *, nombre: str, email: str, telefono: str, documento: str, empresa: str, titulo: str
) -> dict | None:
    to = os.getenv("EVENTS_NOTIFY_EMAIL", "info@auditconsulting.ec").strip()
    html_body = render_charla_aviso_interno(
        nombre=nombre, email=email, telefono=telefono, documento=documento, empresa=empresa, titulo=titulo
    )
    return send_email(to=to, subject=f"Nueva inscripción — {titulo}", html=html_body)
```

- [ ] **Step 6: Correr el test para verificar que pasa**

Run: `python -m pytest tests/test_notifications_charla_email.py -v`
Expected: PASS (4 passed)

- [ ] **Step 7: Commit**

```bash
git add backend/app/notifications/email.py backend/app/notifications/templates/charla_confirmacion.html backend/app/notifications/templates/charla_aviso_interno.html tests/test_notifications_charla_email.py
git commit -m "feat(notifications): emails de confirmación y aviso interno de la charla"
```

---

## Task 7: Orquestación de notificaciones

**Files:**
- Create: `backend/app/events/notify.py`
- Test: `tests/test_events_notify.py`

- [ ] **Step 1: Escribir el test que falla**

Create `tests/test_events_notify.py`:

```python
import uuid

import pytest

from backend.app.db.session import SessionLocal, init_db
from backend.app.events import notify, service
from backend.app.events.models import EventRegistration
from backend.app.events.schemas import RegistrationCreate


@pytest.fixture(autouse=True)
def _db():
    init_db()
    yield


def _make_reg():
    db = SessionLocal()
    try:
        data = RegistrationCreate(
            nombre="María Pérez",
            email=f"n-{uuid.uuid4().hex[:8]}@example.com",
            telefono="0987654321",
            telefono_pais="+593",
            documento="1791240154001",
            empresa="Empresa S.A.",
        )
        reg, _ = service.create_registration(
            db, event_slug="charla-anexos-2026-06", data=data
        )
        return reg.id
    finally:
        db.close()


def test_notify_sets_flags_when_senders_succeed(monkeypatch):
    monkeypatch.setattr(
        notify.email_mod, "send_charla_confirmacion", lambda **k: {"id": "e1"}
    )
    monkeypatch.setattr(
        notify.email_mod, "send_charla_aviso_interno", lambda **k: {"id": "e2"}
    )
    monkeypatch.setattr(
        notify.wa_mod, "send_template_message", lambda **k: {"id": "w1"}
    )

    reg_id = _make_reg()
    notify.process_registration_notifications(reg_id)

    db = SessionLocal()
    try:
        reg = db.get(EventRegistration, reg_id)
        assert reg.email_enviado is True
        assert reg.aviso_interno_enviado is True
        assert reg.whatsapp_enviado is True
    finally:
        db.close()


def test_notify_whatsapp_failure_does_not_break(monkeypatch):
    monkeypatch.setattr(
        notify.email_mod, "send_charla_confirmacion", lambda **k: {"id": "e1"}
    )
    monkeypatch.setattr(
        notify.email_mod, "send_charla_aviso_interno", lambda **k: {"id": "e2"}
    )
    monkeypatch.setattr(notify.wa_mod, "send_template_message", lambda **k: None)

    reg_id = _make_reg()
    notify.process_registration_notifications(reg_id)

    db = SessionLocal()
    try:
        reg = db.get(EventRegistration, reg_id)
        assert reg.email_enviado is True
        assert reg.whatsapp_enviado is False
    finally:
        db.close()


def test_notify_unknown_registration_is_noop():
    # No debe lanzar excepción.
    notify.process_registration_notifications(999999)
```

- [ ] **Step 2: Correr el test para verificar que falla**

Run: `python -m pytest tests/test_events_notify.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'backend.app.events.notify'`

- [ ] **Step 3: Implementar la orquestación**

Create `backend/app/events/notify.py`:

```python
"""Orquestación de notificaciones de una inscripción (corre en BackgroundTask)."""

from __future__ import annotations

import logging

from backend.app.db.session import SessionLocal
from backend.app.events.catalog import get_event
from backend.app.events.models import EventRegistration
from backend.app.notifications import email as email_mod
from backend.app.notifications import whatsapp as wa_mod

log = logging.getLogger(__name__)


def process_registration_notifications(registration_id: int) -> None:
    """Envía confirmación (inscrito) + aviso interno + WhatsApp y persiste los
    flags. Defensivo: ninguna falla individual interrumpe a las demás ni
    propaga excepción al runner de background."""
    db = SessionLocal()
    try:
        reg = db.get(EventRegistration, registration_id)
        if reg is None:
            log.warning("Inscripción %s no encontrada; nada que notificar.", registration_id)
            return
        event = get_event(reg.event_slug)
        if event is None:
            log.warning("Evento %s desconocido para inscripción %s.", reg.event_slug, registration_id)
            return

        # 1. Confirmación al inscrito
        try:
            res = email_mod.send_charla_confirmacion(
                to=reg.email,
                nombre=reg.nombre,
                titulo=event.titulo,
                fecha=event.fecha_texto,
                hora=event.hora_texto,
                modalidad=event.modalidad,
                zoom_url=event.zoom_url,
            )
            reg.email_enviado = res is not None
        except Exception:  # noqa: BLE001
            log.exception("Email de confirmación falló para inscripción %s.", registration_id)

        # 2. Aviso interno a la firma
        try:
            res = email_mod.send_charla_aviso_interno(
                nombre=reg.nombre,
                email=reg.email,
                telefono=reg.telefono_e164,
                documento=reg.documento,
                empresa=reg.empresa,
                titulo=event.titulo,
            )
            reg.aviso_interno_enviado = res is not None
        except Exception:  # noqa: BLE001
            log.exception("Aviso interno falló para inscripción %s.", registration_id)

        # 3. WhatsApp al inscrito
        try:
            res = wa_mod.send_template_message(
                to_e164=reg.telefono_e164,
                variables=[reg.nombre, event.fecha_texto, event.hora_texto],
            )
            reg.whatsapp_enviado = res is not None
        except Exception:  # noqa: BLE001
            log.exception("WhatsApp falló para inscripción %s.", registration_id)

        db.commit()
    finally:
        db.close()
```

- [ ] **Step 4: Correr el test para verificar que pasa**

Run: `python -m pytest tests/test_events_notify.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/events/notify.py tests/test_events_notify.py
git commit -m "feat(events): orquestación de notificaciones email + whatsapp"
```

---

## Task 8: Router (POST público + GET admin) y montaje

**Files:**
- Create: `backend/app/events/router.py`
- Modify: `backend/app/api/__init__.py`
- Test: `tests/test_events_router.py`

- [ ] **Step 1: Escribir el test que falla**

Create `tests/test_events_router.py`:

```python
import uuid

import pytest

from backend.app.auth import service as auth_service
from backend.app.auth.models import Role
from backend.app.client_portal.rate_limit import reset_for_key
from backend.app.db.session import SessionLocal, init_db


@pytest.fixture(autouse=True)
def _db():
    init_db()
    yield


@pytest.fixture(autouse=True)
def _no_real_notify(monkeypatch):
    # Evita red real / sleeps de backoff en los tests del router.
    monkeypatch.setattr(
        "backend.app.events.notify.process_registration_notifications",
        lambda *a, **k: None,
    )


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    reset_for_key("event-reg:testclient")
    yield
    reset_for_key("event-reg:testclient")


SLUG = "charla-anexos-2026-06"


def _payload(email=None):
    return {
        "nombre": "María Pérez",
        "email": email or f"r-{uuid.uuid4().hex[:8]}@example.com",
        "telefono": "0987654321",
        "telefono_pais": "+593",
        "documento": "1791240154001",
        "empresa": "Empresa S.A.",
    }


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


def test_register_ok_201(client):
    r = client.post(f"/api/v1/events/{SLUG}/registrations", json=_payload())
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["ya_inscrito"] is False


def test_register_idempotent(client):
    email = f"r-{uuid.uuid4().hex[:8]}@example.com"
    client.post(f"/api/v1/events/{SLUG}/registrations", json=_payload(email))
    r2 = client.post(f"/api/v1/events/{SLUG}/registrations", json=_payload(email))
    assert r2.status_code == 201, r2.text
    assert r2.json()["ya_inscrito"] is True


def test_register_unknown_slug_404(client):
    r = client.post("/api/v1/events/no-existe/registrations", json=_payload())
    assert r.status_code == 404


def test_register_invalid_documento_422(client):
    bad = _payload()
    bad["documento"] = "123"
    r = client.post(f"/api/v1/events/{SLUG}/registrations", json=bad)
    assert r.status_code == 422


def test_rate_limit_429(client):
    last = None
    for _ in range(11):
        last = client.post(f"/api/v1/events/{SLUG}/registrations", json=_payload())
    assert last.status_code == 429


def test_list_requires_admin(client):
    r = client.get(f"/api/v1/events/{SLUG}/registrations")
    assert r.status_code == 401


def test_list_with_admin_ok(client):
    client.post(f"/api/v1/events/{SLUG}/registrations", json=_payload())
    tok = _admin_token(client)
    r = client.get(
        f"/api/v1/events/{SLUG}/registrations",
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)
```

- [ ] **Step 2: Correr el test para verificar que falla**

Run: `python -m pytest tests/test_events_router.py -v`
Expected: FAIL (404 en todas las rutas porque el router no está montado / `ModuleNotFoundError`).

- [ ] **Step 3: Implementar el router**

Create `backend/app/events/router.py`:

```python
"""Endpoints /api/v1/events/* — inscripción pública + listado admin."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.app.auth.deps import require_admin
from backend.app.client_portal.rate_limit import check_and_record
from backend.app.db.session import get_db
from backend.app.events import notify, service
from backend.app.events.catalog import get_event
from backend.app.events.schemas import (
    RegistrationCreate,
    RegistrationOut,
    RegistrationResponse,
)

router = APIRouter(prefix="/events", tags=["events"])


@router.post(
    "/{slug}/registrations",
    response_model=RegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_registration_endpoint(
    slug: str,
    payload: RegistrationCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
):
    event = get_event(slug)
    if event is None or not event.activo:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Evento no encontrado o inactivo.")

    ip = request.client.host if request.client else "unknown"
    if not check_and_record(f"event-reg:{ip}", max_hits=10, window_seconds=600):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiadas inscripciones desde esta red. Intente más tarde.",
        )

    reg, ya_inscrito = service.create_registration(db, event_slug=slug, data=payload)
    background_tasks.add_task(notify.process_registration_notifications, reg.id)

    mensaje = (
        "Ya estabas inscrito; te reenviamos los detalles por email y WhatsApp."
        if ya_inscrito
        else "Inscripción confirmada. Te enviamos los detalles por email y WhatsApp."
    )
    return RegistrationResponse(
        ok=True, estado=reg.estado, ya_inscrito=ya_inscrito, mensaje=mensaje
    )


@router.get(
    "/{slug}/registrations",
    response_model=list[RegistrationOut],
    dependencies=[Depends(require_admin)],
)
def list_registrations_endpoint(
    slug: str,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    rows = service.list_registrations(db, event_slug=slug, limit=limit)
    return [RegistrationOut.model_validate(r) for r in rows]
```

- [ ] **Step 4: Montar el router en el api_router**

In `backend/app/api/__init__.py`:

Añadir el import junto a los demás (después de `from backend.app.context import router as context_router`):

```python
from backend.app.events import router as events_router
```

Añadir la línea de montaje (después de `api_router.include_router(ict_router)`):

```python
api_router.include_router(events_router.router)
```

- [ ] **Step 5: Correr el test para verificar que pasa**

Run: `python -m pytest tests/test_events_router.py -v`
Expected: PASS (7 passed)

- [ ] **Step 6: Commit**

```bash
git add backend/app/events/router.py backend/app/api/__init__.py tests/test_events_router.py
git commit -m "feat(events): router público de inscripción + listado admin"
```

---

## Task 9: API del frontend (`registrarCharla`)

**Files:**
- Modify: `frontend-client/src/api.js`

- [ ] **Step 1: Añadir la función al final de `frontend-client/src/api.js`**

```javascript
// --- Inscripción pública a eventos (charlas). Endpoint sin auth. ---
export async function registrarCharla(slug, payload) {
  const resp = await fetch(`${BASE}/api/v1/events/${slug}/registrations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  let body = null;
  try { body = await resp.json(); } catch { /* ignore */ }
  if (!resp.ok) {
    const detail = body?.detail;
    const msg = typeof detail === "string" ? detail
      : detail?.message || "No se pudo completar la inscripción. Revisa los datos.";
    const err = new Error(msg);
    err.status = resp.status;
    throw err;
  }
  return body;
}
```

- [ ] **Step 2: Verificar que el build no rompe**

Run: `cd frontend-client && npm run build`
Expected: build OK (sin errores de sintaxis). Si `node_modules` no existe, primero `npm install`.

- [ ] **Step 3: Commit**

```bash
git add frontend-client/src/api.js
git commit -m "feat(frontend-client): cliente API registrarCharla"
```

---

## Task 10: Formulario de inscripción (`CharlaForm.jsx`)

**Files:**
- Create: `frontend-client/src/charla/CharlaForm.jsx`
- Create: `frontend-client/src/charla/charla.css`

- [ ] **Step 1: Crear los estilos**

Create `frontend-client/src/charla/charla.css`:

```css
.charla-page { background:#0a2540; color:#e6edf3; min-height:100vh; font-family:Arial, Helvetica, sans-serif; }
.charla-wrap { max-width:1040px; margin:0 auto; padding:32px 20px 64px; }
.charla-hero { display:grid; grid-template-columns:1fr; gap:24px; }
@media (min-width:880px){ .charla-hero{ grid-template-columns:1.1fr 0.9fr; align-items:start; } }
.charla-badge { display:inline-block; background:rgba(139,195,74,.15); color:#a5d66a; border:1px solid #8bc34a; border-radius:999px; padding:6px 14px; font-size:13px; font-weight:bold; letter-spacing:.5px; }
.charla-title { font-size:34px; line-height:1.1; margin:14px 0 8px; color:#fff; text-transform:uppercase; }
.charla-title b { color:#8bc34a; }
.charla-sub { color:#9fb3c8; font-size:16px; margin:0 0 20px; }
.charla-meta { display:flex; flex-wrap:wrap; gap:12px; margin:18px 0; }
.charla-meta div { background:rgba(255,255,255,.05); border:1px solid rgba(255,255,255,.08); border-radius:10px; padding:10px 14px; min-width:120px; }
.charla-meta span { display:block; color:#9fb3c8; font-size:12px; }
.charla-meta b { font-size:16px; color:#fff; }
.charla-benefits { list-style:none; padding:0; margin:18px 0; }
.charla-benefits li { padding:7px 0 7px 28px; position:relative; color:#cdd9e5; }
.charla-benefits li::before { content:"✓"; position:absolute; left:0; color:#8bc34a; font-weight:bold; }
.charla-card { background:#fff; color:#0a2540; border-radius:16px; padding:24px; box-shadow:0 20px 50px rgba(0,0,0,.35); }
.charla-card h3 { margin:0 0 4px; font-size:20px; }
.charla-card p.lead { margin:0 0 18px; color:#64748b; font-size:14px; }
.charla-field { margin-bottom:14px; }
.charla-field label { display:block; font-size:13px; font-weight:bold; margin-bottom:5px; color:#334155; }
.charla-field input { width:100%; box-sizing:border-box; padding:11px 12px; border:1px solid #cbd5e1; border-radius:8px; font-size:15px; }
.charla-phone { display:grid; grid-template-columns:84px 1fr; gap:8px; }
.charla-btn { width:100%; background:#8bc34a; color:#0a2540; border:none; border-radius:10px; padding:14px; font-size:16px; font-weight:bold; cursor:pointer; }
.charla-btn:disabled { opacity:.6; cursor:not-allowed; }
.charla-err { background:#fde8e8; color:#9b1c1c; border:1px solid #f5c2c2; border-radius:8px; padding:10px 12px; font-size:14px; margin-bottom:12px; }
.charla-success { text-align:center; padding:18px 4px; }
.charla-success .check { font-size:46px; color:#8bc34a; }
.charla-success h3 { color:#0a2540; margin:8px 0; }
.charla-foot { text-align:center; color:#9fb3c8; font-size:12px; padding:24px 0 0; }
```

- [ ] **Step 2: Crear el formulario**

Create `frontend-client/src/charla/CharlaForm.jsx`:

```jsx
import { useState } from "react";
import { registrarCharla } from "../api.js";

const SLUG = "charla-anexos-2026-06";

const EMPTY = {
  nombre: "",
  email: "",
  telefono_pais: "+593",
  telefono: "",
  documento: "",
  empresa: "",
};

export default function CharlaForm({ evento, onSuccess }) {
  const [form, setForm] = useState(EMPTY);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  function set(field, value) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  function validateClient() {
    if (form.nombre.trim().length < 3) return "Ingresa tu nombre y apellido.";
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(form.email)) return "Ingresa un email válido.";
    const tel = form.telefono.replace(/\D/g, "");
    if (tel.length < 7) return "Ingresa un número de celular válido.";
    const doc = form.documento.replace(/\D/g, "");
    if (doc.length !== 10 && doc.length !== 13) return "La cédula debe tener 10 dígitos o el RUC 13.";
    if (form.empresa.trim().length < 1) return "Ingresa el nombre de tu empresa.";
    return "";
  }

  async function submit(e) {
    e.preventDefault();
    const v = validateClient();
    if (v) { setErr(v); return; }
    setErr("");
    setBusy(true);
    try {
      const res = await registrarCharla(SLUG, {
        nombre: form.nombre.trim(),
        email: form.email.trim(),
        telefono: form.telefono.trim(),
        telefono_pais: form.telefono_pais.trim(),
        documento: form.documento.trim(),
        empresa: form.empresa.trim(),
      });
      onSuccess(res);
    } catch (e2) {
      setErr(e2.message || "No se pudo completar la inscripción.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="charla-card">
      <h3>Reserva tu cupo gratis</h3>
      <p className="lead">Cupos limitados · {evento.modalidad}</p>
      {err && <div className="charla-err">{err}</div>}
      <form onSubmit={submit}>
        <div className="charla-field">
          <label>Nombre y apellido</label>
          <input value={form.nombre} onChange={(e) => set("nombre", e.target.value)} required />
        </div>
        <div className="charla-field">
          <label>Email</label>
          <input type="email" value={form.email} onChange={(e) => set("email", e.target.value)} required />
        </div>
        <div className="charla-field">
          <label>Celular (WhatsApp)</label>
          <div className="charla-phone">
            <input value={form.telefono_pais} onChange={(e) => set("telefono_pais", e.target.value)} aria-label="Código de país" />
            <input value={form.telefono} onChange={(e) => set("telefono", e.target.value)} placeholder="0987654321" required />
          </div>
        </div>
        <div className="charla-field">
          <label>Cédula o RUC</label>
          <input value={form.documento} onChange={(e) => set("documento", e.target.value)} required />
        </div>
        <div className="charla-field">
          <label>Empresa</label>
          <input value={form.empresa} onChange={(e) => set("empresa", e.target.value)} required />
        </div>
        <button className="charla-btn" disabled={busy}>
          {busy ? "Enviando…" : "¡Registrarme gratis!"}
        </button>
      </form>
    </div>
  );
}
```

- [ ] **Step 3: Verificar build**

Run: `cd frontend-client && npm run build`
Expected: build OK.

- [ ] **Step 4: Commit**

```bash
git add frontend-client/src/charla/CharlaForm.jsx frontend-client/src/charla/charla.css
git commit -m "feat(frontend-client): formulario de inscripción a la charla"
```

---

## Task 11: Página landing (`CharlaLanding.jsx`)

**Files:**
- Create: `frontend-client/src/charla/CharlaLanding.jsx`

> Los datos del evento se mantienen en el frontend como constante de presentación, coherentes con el catálogo backend (`backend/app/events/catalog.py`). El backend es la fuente de verdad para la lógica; el front solo los muestra.

- [ ] **Step 1: Crear la landing**

Create `frontend-client/src/charla/CharlaLanding.jsx`:

```jsx
import { useState } from "react";
import CharlaForm from "./CharlaForm.jsx";
import "./charla.css";

const EVENTO = {
  titulo: "Elaboración de Anexos Tributarios con Herramienta de Automatización",
  subtitulo: "Charla gratuita en Zoom",
  fecha: "Jueves 18 de junio",
  hora: "19h00",
  duracion: "2 horas",
  modalidad: "Zoom",
  beneficios: [
    "Automatiza tus anexos tributarios",
    "Descarga inteligente de información del SRI",
    "Validaciones automáticas y control de inconsistencias",
    "Reduce tiempos y minimiza errores",
    "Casos prácticos para empresas y profesionales",
  ],
};

function Exito({ evento }) {
  return (
    <div className="charla-card">
      <div className="charla-success">
        <div className="check">✓</div>
        <h3>¡Reserva confirmada!</h3>
        <p>Te enviamos los detalles a tu email y WhatsApp.</p>
        <div className="charla-meta" style={{ justifyContent: "center" }}>
          <div><span>Fecha</span><b>{evento.fecha}</b></div>
          <div><span>Hora</span><b>{evento.hora}</b></div>
          <div><span>Modalidad</span><b>{evento.modalidad}</b></div>
        </div>
      </div>
    </div>
  );
}

export default function CharlaLanding() {
  const [done, setDone] = useState(false);

  return (
    <div className="charla-page">
      <div className="charla-wrap">
        <div className="charla-hero">
          <div>
            <span className="charla-badge">{EVENTO.subtitulo}</span>
            <h1 className="charla-title">
              Elaboración de <b>Anexos Tributarios</b> con Herramienta de Automatización
            </h1>
            <p className="charla-sub">Más eficiencia, menos errores, cumplimiento asegurado.</p>
            <div className="charla-meta">
              <div><span>Fecha</span><b>{EVENTO.fecha}</b></div>
              <div><span>Hora</span><b>{EVENTO.hora}</b></div>
              <div><span>Duración</span><b>{EVENTO.duracion}</b></div>
              <div><span>Modalidad</span><b>{EVENTO.modalidad}</b></div>
            </div>
            <ul className="charla-benefits">
              {EVENTO.beneficios.map((b) => <li key={b}>{b}</li>)}
            </ul>
          </div>
          {done ? <Exito evento={EVENTO} /> : <CharlaForm evento={EVENTO} onSuccess={() => setDone(true)} />}
        </div>
        <div className="charla-foot">
          © {new Date().getFullYear()} Audit Consulting Group · Powered by Audit-IA
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verificar build**

Run: `cd frontend-client && npm run build`
Expected: build OK.

- [ ] **Step 3: Commit**

```bash
git add frontend-client/src/charla/CharlaLanding.jsx
git commit -m "feat(frontend-client): página landing de la charla"
```

---

## Task 12: Ruta `/charla` en el router

**Files:**
- Modify: `frontend-client/src/App.jsx`

- [ ] **Step 1: Añadir el import y la ruta**

In `frontend-client/src/App.jsx`:

Añadir el import (junto a los demás imports de páginas, después de `import Landing from "./landing/Landing.jsx";`):

```javascript
import CharlaLanding from "./charla/CharlaLanding.jsx";
```

Añadir la ruta dentro de `<Routes>` (después de `<Route path="/" element={<Landing />} />`):

```jsx
      <Route path="/charla" element={<CharlaLanding />} />
```

- [ ] **Step 2: Verificar build**

Run: `cd frontend-client && npm run build`
Expected: build OK.

- [ ] **Step 3: Commit**

```bash
git add frontend-client/src/App.jsx
git commit -m "feat(frontend-client): ruta pública /charla"
```

---

## Task 13: Verificación empírica final (regla suprema CLAUDE.md)

**Files:** ninguno (solo verificación).

- [ ] **Step 1: Correr toda la suite de tests de eventos y notificaciones**

Run:
```bash
python -m pytest tests/test_events_catalog.py tests/test_events_models.py tests/test_events_schemas.py tests/test_events_service.py tests/test_notifications_whatsapp.py tests/test_notifications_charla_email.py tests/test_events_notify.py tests/test_events_router.py -v
```
Expected: TODOS en verde (PASS). Reportar el conteo exacto.

- [ ] **Step 2: Confirmar que no se rompió la suite existente**

Run: `python -m pytest tests/ -q --tb=short`
Expected: los mismos fallos pre-existentes documentados en `CLAUDE.md` (5 tests legacy: `test_chat`/`test_context`/`test_sandbox`) y NADA nuevo roto. Reportar honestamente cualquier fallo adicional.

- [ ] **Step 3: Levantar la landing localmente y verificar el flujo end-to-end**

En una terminal, levantar el backend:
```bash
uvicorn app:app --port 8000
```
En otra, el frontend con la base apuntando al backend local:
```bash
cd frontend-client && VITE_API_BASE=http://localhost:8000 npm run dev
```
Abrir `http://localhost:5174/charla`, llenar el formulario con datos de prueba y enviar.

Verificar:
- Aparece la pantalla "¡Reserva confirmada!".
- Consultar la BD (admin): obtener token admin y `GET /api/v1/events/charla-anexos-2026-06/registrations` devuelve la fila recién creada.
- Los flags `email_enviado` / `whatsapp_enviado` reflejan el estado real (serán `false` si no hay `RESEND_API_KEY` / `WHATSAPP_*` configurados localmente — comportamiento esperado de degradación elegante).

- [ ] **Step 4: Verificar normalización del teléfono con dato real**

Tras inscribir con teléfono `0987654321` y país `+593`, confirmar en la respuesta admin que `telefono_e164 == "+593987654321"`.

- [ ] **Step 5: Documentar las env vars nuevas**

Verificar/añadir en el README o `docs/DEPLOYMENT.md` la tabla de env vars nuevas: `CHARLA_ZOOM_URL`, `EVENTS_NOTIFY_EMAIL`, `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_TEMPLATE_NAME`, `WHATSAPP_TEMPLATE_LANG`.

- [ ] **Step 6: Commit final**

```bash
git add -A
git commit -m "docs(events): env vars de la landing de charla + verificación"
```

---

## Self-Review (cobertura del spec)

| Requisito del spec | Task que lo implementa |
|---|---|
| Landing pública en `frontend-client` `/charla` | Task 11, 12 |
| Formulario: nombre, email, celular, cédula/RUC, empresa | Task 10 |
| Persistencia en Postgres (`EventRegistration`) | Task 2 |
| Inscripción idempotente (slug+email) | Task 2 (constraint), Task 4 (servicio) |
| Endpoint público + rate-limit | Task 8 |
| Endpoint admin de listado | Task 8 |
| Email de confirmación (Resend) | Task 6 |
| Email aviso interno a la firma | Task 6 |
| WhatsApp Cloud API + degradación elegante | Task 5, 7 |
| Normalización E.164 + validación documento | Task 3 |
| Evento configurable (catálogo + Zoom URL env) | Task 1 |
| BackgroundTasks para notificar | Task 8 (dispatch), Task 7 (lógica) |
| Tests de todo lo anterior | Tasks 1–8 |
| Verificación empírica end-to-end | Task 13 |

**Placeholder scan:** sin "TBD"/"TODO"/pasos vacíos; todo paso de código incluye el código real.

**Consistencia de tipos/nombres:** `create_registration` devuelve `(reg, ya_inscrito)` y así se consume en Task 8. `send_template_message(to_e164=, variables=)` definido en Task 5 y llamado idéntico en Task 7. `send_charla_confirmacion`/`send_charla_aviso_interno` definidos en Task 6 y llamados idénticos en Task 7. `RegistrationCreate.telefono_e164` calculado en Task 3 y usado en Task 4. Slug `charla-anexos-2026-06` consistente en backend (Task 1) y frontend (Task 10).
