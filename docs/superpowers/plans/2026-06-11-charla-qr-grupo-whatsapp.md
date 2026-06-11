# Charla — QR a grupo de WhatsApp + protección de datos (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reemplazar la confirmación por WhatsApp Cloud API por una segunda pantalla con un código QR que lleva al grupo de WhatsApp de la charla, y añadir un texto informativo de protección de datos (LOPDP Ecuador) en el formulario, la pantalla del QR y el email.

**Architecture:** Delta sobre la landing ya implementada (PR #41, branch `feat/landing-charla-inscripcion`). Backend: se elimina el módulo WhatsApp Cloud API, el catálogo gana `whatsapp_group_url` (env `CHARLA_WHATSAPP_GROUP_URL`) y el endpoint lo devuelve en la respuesta; el email suma botón de grupo + texto legal. Frontend: la pantalla de éxito muestra un QR (`qrcode.react`) del link del grupo + texto legal.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.0, Pydantic 2.8.2, pytest, React 18, Vite, `qrcode.react` v3.

**Idioma:** comunicación con el usuario en español. Commits en español, terminando con la línea `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

> **Git:** branch `feat/landing-charla-inscripcion`. `git add` SIEMPRE dirigido (archivos exactos), NUNCA `git add -A` — hay untracked files ajenos (`docs/gpt/`, `scripts/*.py`) que NO se tocan.

---

## File Structure

**Eliminar:**
- `backend/app/notifications/whatsapp.py`
- `tests/test_notifications_whatsapp.py`

**Crear:**
- `backend/app/events/legal.py` — texto de protección de datos reutilizable.
- `frontend-client/src/charla/legal.js` — copia del texto legal para el front.
- `tests/test_events_legal.py`

**Modificar (backend):**
- `backend/app/events/catalog.py` — campo `whatsapp_group_url`.
- `backend/app/events/models.py` — quitar columna `whatsapp_enviado`.
- `backend/app/events/schemas.py` — `RegistrationResponse.whatsapp_group_url`; quitar `whatsapp_enviado` de `RegistrationOut`.
- `backend/app/events/router.py` — devolver `whatsapp_group_url`; ajustar mensaje.
- `backend/app/events/notify.py` — quitar WhatsApp; pasar grupo + contacto al email.
- `backend/app/notifications/email.py` — confirmación con botón de grupo + texto legal.
- `backend/app/notifications/templates/charla_confirmacion.html` — placeholders `{{grupo_block}}` y `{{proteccion_datos}}`.

**Modificar (frontend):**
- `frontend-client/package.json` — dependencia `qrcode.react`.
- `frontend-client/src/charla/CharlaLanding.jsx` — segunda pantalla con QR + legal.
- `frontend-client/src/charla/CharlaForm.jsx` — texto legal bajo el formulario.
- `frontend-client/src/charla/charla.css` — estilos QR + legal.

**Modificar (tests):**
- `tests/test_events_models.py`, `tests/test_events_notify.py`, `tests/test_events_router.py`, `tests/test_notifications_charla_email.py`.

---

## Task 1: Backend — eliminar WhatsApp Cloud API

**Files:**
- Delete: `backend/app/notifications/whatsapp.py`, `tests/test_notifications_whatsapp.py`
- Modify: `backend/app/events/models.py`, `backend/app/events/schemas.py`, `backend/app/events/notify.py`
- Modify (tests): `tests/test_events_models.py`, `tests/test_events_notify.py`

- [ ] **Step 1: Borrar los archivos de WhatsApp Cloud API**

```bash
git rm backend/app/notifications/whatsapp.py tests/test_notifications_whatsapp.py
```

- [ ] **Step 2: Quitar la columna `whatsapp_enviado` del modelo**

In `backend/app/events/models.py`, eliminá esta línea (línea 30):

```python
    whatsapp_enviado: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
```

(Quedan `email_enviado` y `aviso_interno_enviado`.)

- [ ] **Step 3: Quitar `whatsapp_enviado` de `RegistrationOut`**

In `backend/app/events/schemas.py`, eliminá esta línea de `RegistrationOut` (línea 68):

```python
    whatsapp_enviado: bool
```

- [ ] **Step 4: Reescribir `notify.py` sin WhatsApp (y con grupo + contacto en el email)**

Reemplazá TODO el contenido de `backend/app/events/notify.py` por:

```python
"""Orquestación de notificaciones de una inscripción (corre en BackgroundTask)."""

from __future__ import annotations

import logging
import os

from backend.app.db.session import SessionLocal
from backend.app.events.catalog import get_event
from backend.app.events.models import EventRegistration
from backend.app.notifications import email as email_mod

log = logging.getLogger(__name__)


def process_registration_notifications(registration_id: int) -> None:
    """Envía confirmación (inscrito) + aviso interno y persiste los flags.
    Defensivo: ninguna falla individual interrumpe a las demás ni propaga
    excepción al runner de background."""
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

        contacto = os.getenv(
            "DATA_PROTECTION_CONTACT_EMAIL", "info@auditconsulting.ec"
        ).strip()

        # 1. Confirmación al inscrito (incluye botón al grupo de WhatsApp + texto legal)
        try:
            res = email_mod.send_charla_confirmacion(
                to=reg.email,
                nombre=reg.nombre,
                titulo=event.titulo,
                fecha=event.fecha_texto,
                hora=event.hora_texto,
                modalidad=event.modalidad,
                zoom_url=event.zoom_url,
                whatsapp_group_url=event.whatsapp_group_url,
                data_protection_contact=contacto,
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

        try:
            db.commit()
        except Exception:  # noqa: BLE001
            log.exception(
                "Error al persistir flags de notificación para inscripción %s.",
                registration_id,
            )
    finally:
        db.close()
```

- [ ] **Step 5: Actualizar `tests/test_events_models.py`**

Eliminá esta línea del test `test_can_insert_registration`:

```python
        assert reg.whatsapp_enviado is False
```

- [ ] **Step 6: Reescribir `tests/test_events_notify.py` (sin WhatsApp)**

Reemplazá TODO el contenido de `tests/test_events_notify.py` por:

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

    reg_id = _make_reg()
    notify.process_registration_notifications(reg_id)

    db = SessionLocal()
    try:
        reg = db.get(EventRegistration, reg_id)
        assert reg.email_enviado is True
        assert reg.aviso_interno_enviado is True
    finally:
        db.close()


def test_notify_email_failure_does_not_break(monkeypatch):
    monkeypatch.setattr(
        notify.email_mod, "send_charla_confirmacion", lambda **k: None
    )
    monkeypatch.setattr(
        notify.email_mod, "send_charla_aviso_interno", lambda **k: {"id": "e2"}
    )

    reg_id = _make_reg()
    notify.process_registration_notifications(reg_id)

    db = SessionLocal()
    try:
        reg = db.get(EventRegistration, reg_id)
        assert reg.email_enviado is False
        assert reg.aviso_interno_enviado is True
    finally:
        db.close()


def test_notify_unknown_registration_is_noop():
    # No debe lanzar excepción.
    notify.process_registration_notifications(999999)
```

- [ ] **Step 7: Correr los tests afectados (deben fallar/pasar coherentemente)**

Run: `python -m pytest tests/test_events_models.py tests/test_events_notify.py -v`
Expected: PASS. (El `notify.py` ya no importa `whatsapp`; los tests no referencian WhatsApp.)

> Nota: en este punto `email_mod.send_charla_confirmacion` todavía NO acepta `whatsapp_group_url`/`data_protection_contact`. El test de notify lo monkeypatchea con `lambda **k`, así que pasa igual. La firma real se actualiza en la Task 3; el `notify.py` ya la invoca con los kwargs nuevos, lo cual quedará consistente tras la Task 3. Si querés correr el flujo real entre Task 1 y 3 fallaría por kwargs; los tests con monkeypatch NO fallan.

- [ ] **Step 8: Commit**

```bash
git add backend/app/notifications/whatsapp.py tests/test_notifications_whatsapp.py backend/app/events/models.py backend/app/events/schemas.py backend/app/events/notify.py tests/test_events_models.py tests/test_events_notify.py
git commit -m "refactor(events): elimina WhatsApp Cloud API (canal pasa a grupo via QR)"
```

(El `git rm` del Step 1 ya stageó los borrados; `git add` de las rutas borradas es idempotente.)

---

## Task 2: Backend — config del grupo, texto legal y respuesta del endpoint

**Files:**
- Create: `backend/app/events/legal.py`, `tests/test_events_legal.py`
- Modify: `backend/app/events/catalog.py`, `backend/app/events/schemas.py`, `backend/app/events/router.py`
- Modify (test): `tests/test_events_router.py`

- [ ] **Step 1: Escribir el test del texto legal (falla)**

Create `tests/test_events_legal.py`:

```python
from backend.app.events.legal import data_protection_text


def test_data_protection_text_includes_contact_and_law():
    txt = data_protection_text("datos@x.ec")
    assert "datos@x.ec" in txt
    assert "Protección de Datos Personales" in txt
    assert "Audit Consulting Group" in txt
```

- [ ] **Step 2: Correr para verificar que falla**

Run: `python -m pytest tests/test_events_legal.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'backend.app.events.legal'`

- [ ] **Step 3: Crear `backend/app/events/legal.py`**

```python
"""Textos legales reutilizables del módulo de eventos (LOPDP Ecuador)."""

from __future__ import annotations


def data_protection_text(contacto: str) -> str:
    """Aviso informativo de protección de datos (sin checkbox de consentimiento)."""
    return (
        "Audit Consulting Group trata tus datos (nombre, correo, teléfono, "
        "identificación, empresa) para gestionar tu inscripción y enviarte "
        "información de la charla, conforme a la Ley Orgánica de Protección de "
        "Datos Personales del Ecuador. Podés ejercer tus derechos de acceso, "
        f"rectificación y eliminación escribiendo a {contacto}."
    )
```

- [ ] **Step 4: Correr para verificar que pasa**

Run: `python -m pytest tests/test_events_legal.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Añadir `whatsapp_group_url` al catálogo**

In `backend/app/events/catalog.py`:

(a) En la dataclass `EventInfo`, añadí el campo `whatsapp_group_url` justo después de `zoom_url`:

```python
    zoom_url: str
    whatsapp_group_url: str
    beneficios: list[str] = field(default_factory=list)
```

(b) En `_build_events`, después de la línea `zoom_url=os.getenv("CHARLA_ZOOM_URL", ""),`, añadí:

```python
        whatsapp_group_url=os.getenv("CHARLA_WHATSAPP_GROUP_URL", ""),
```

- [ ] **Step 6: Añadir `whatsapp_group_url` a `RegistrationResponse`**

In `backend/app/events/schemas.py`, reemplazá la clase `RegistrationResponse` por:

```python
class RegistrationResponse(BaseModel):
    ok: bool
    estado: str
    ya_inscrito: bool
    mensaje: str
    whatsapp_group_url: str = ""
```

- [ ] **Step 7: Devolver `whatsapp_group_url` y ajustar el mensaje en el router**

In `backend/app/events/router.py`, reemplazá el bloque `mensaje = (...)` + `return RegistrationResponse(...)` (líneas 57-64) por:

```python
    mensaje = (
        "Ya estabas inscrito. Escaneá el QR para unirte al grupo de WhatsApp; también te reenviamos el email."
        if ya_inscrito
        else "Inscripción confirmada. Escaneá el QR para unirte al grupo de WhatsApp; te enviamos los detalles por email."
    )
    return RegistrationResponse(
        ok=True,
        estado=reg.estado,
        ya_inscrito=ya_inscrito,
        mensaje=mensaje,
        whatsapp_group_url=event.whatsapp_group_url,
    )
```

- [ ] **Step 8: Añadir test al router que verifica el campo nuevo**

In `tests/test_events_router.py`, añadí esta función de test (después de `test_register_ok_201`):

```python
def test_register_response_includes_group_url(client):
    r = client.post(f"/api/v1/events/{SLUG}/registrations", json=_payload())
    assert r.status_code == 201, r.text
    assert "whatsapp_group_url" in r.json()
```

- [ ] **Step 9: Correr los tests del router + catálogo + legal**

Run: `python -m pytest tests/test_events_router.py tests/test_events_catalog.py tests/test_events_legal.py -v`
Expected: PASS (todos).

- [ ] **Step 10: Commit**

```bash
git add backend/app/events/legal.py tests/test_events_legal.py backend/app/events/catalog.py backend/app/events/schemas.py backend/app/events/router.py tests/test_events_router.py
git commit -m "feat(events): grupo de WhatsApp en catalogo/respuesta + texto LOPDP"
```

---

## Task 3: Backend — email con botón de grupo + texto de protección de datos

**Files:**
- Modify: `backend/app/notifications/templates/charla_confirmacion.html`
- Modify: `backend/app/notifications/email.py`
- Modify (test): `tests/test_notifications_charla_email.py`

- [ ] **Step 1: Actualizar la plantilla de email**

Reemplazá TODO el contenido de `backend/app/notifications/templates/charla_confirmacion.html` por:

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
    {{grupo_block}}
    {{zoom_block}}
    <p style="color:#94a3b8;font-size:11px;line-height:1.5;border-top:1px solid #e2e8f0;padding-top:14px;margin-top:24px">
      {{proteccion_datos}}
    </p>
  </div>
</body>
</html>
```

- [ ] **Step 2: Actualizar el render del email (botón de grupo + legal)**

In `backend/app/notifications/email.py`, reemplazá la función `render_charla_confirmacion` (líneas 80-100) por:

```python
def render_charla_confirmacion(
    *,
    nombre: str,
    titulo: str,
    fecha: str,
    hora: str,
    modalidad: str,
    zoom_url: str,
    whatsapp_group_url: str = "",
    data_protection_contact: str = "info@auditconsulting.ec",
) -> str:
    from backend.app.events.legal import data_protection_text

    tpl = (_TEMPLATES_DIR / "charla_confirmacion.html").read_text(encoding="utf-8")
    if zoom_url:
        zoom_block = (
            '<p style="text-align:center;margin:8px 0 18px">'
            f'<a href="{_html.escape(zoom_url, quote=True)}" '
            'style="background:#0a2540;color:#fff;font-weight:bold;padding:12px 28px;'
            'text-decoration:none;border-radius:6px;display:inline-block">Unirme por Zoom</a></p>'
        )
    else:
        zoom_block = ""
    if whatsapp_group_url:
        grupo_block = (
            '<p style="color:#334155;font-size:14px;margin:14px 0 4px">'
            'Unite al grupo de WhatsApp donde compartiremos el link de la charla:</p>'
            '<p style="text-align:center;margin:8px 0 18px">'
            f'<a href="{_html.escape(whatsapp_group_url, quote=True)}" '
            'style="background:#8bc34a;color:#0a2540;font-weight:bold;padding:12px 28px;'
            'text-decoration:none;border-radius:6px;display:inline-block">Unirme al grupo de WhatsApp</a></p>'
        )
    else:
        grupo_block = ""
    proteccion = _html.escape(data_protection_text(data_protection_contact))
    return (
        tpl.replace("{{nombre}}", _html.escape(nombre))
        .replace("{{titulo}}", _html.escape(titulo))
        .replace("{{fecha}}", _html.escape(fecha))
        .replace("{{hora}}", _html.escape(hora))
        .replace("{{modalidad}}", _html.escape(modalidad))
        .replace("{{zoom_block}}", zoom_block)
        .replace("{{grupo_block}}", grupo_block)
        .replace("{{proteccion_datos}}", proteccion)
    )
```

- [ ] **Step 3: Actualizar la firma de `send_charla_confirmacion`**

In `backend/app/notifications/email.py`, reemplazá la función `send_charla_confirmacion` (líneas 103-111) por:

```python
def send_charla_confirmacion(
    *,
    to: str,
    nombre: str,
    titulo: str,
    fecha: str,
    hora: str,
    modalidad: str,
    zoom_url: str,
    whatsapp_group_url: str = "",
    data_protection_contact: str = "info@auditconsulting.ec",
) -> dict | None:
    html_body = render_charla_confirmacion(
        nombre=nombre,
        titulo=titulo,
        fecha=fecha,
        hora=hora,
        modalidad=modalidad,
        zoom_url=zoom_url,
        whatsapp_group_url=whatsapp_group_url,
        data_protection_contact=data_protection_contact,
    )
    return send_email(
        to=to, subject=f"Confirmación de tu reserva — {titulo}", html=html_body
    )
```

- [ ] **Step 4: Añadir test del email con grupo + protección de datos**

In `tests/test_notifications_charla_email.py`, añadí esta función de test (después de `test_render_confirmacion_without_zoom_url_no_button`):

```python
def test_render_confirmacion_with_group_and_data_protection():
    html = email_mod.render_charla_confirmacion(
        nombre="María",
        titulo="T",
        fecha="F",
        hora="H",
        modalidad="Zoom",
        zoom_url="",
        whatsapp_group_url="https://chat.whatsapp.com/ABC123",
        data_protection_contact="datos@auditconsulting.ec",
    )
    assert "https://chat.whatsapp.com/ABC123" in html
    assert "Unirme al grupo de WhatsApp" in html
    assert "Protección de Datos Personales" in html
    assert "datos@auditconsulting.ec" in html
    assert "{{" not in html
```

- [ ] **Step 5: Correr los tests de email**

Run: `python -m pytest tests/test_notifications_charla_email.py -v`
Expected: PASS (5 passed — los 4 previos siguen verdes porque los params nuevos tienen default).

- [ ] **Step 6: Commit**

```bash
git add backend/app/notifications/templates/charla_confirmacion.html backend/app/notifications/email.py tests/test_notifications_charla_email.py
git commit -m "feat(notifications): email con boton al grupo de WhatsApp + texto LOPDP"
```

---

## Task 4: Frontend — segunda pantalla con QR + texto de protección de datos

**Files:**
- Modify: `frontend-client/package.json`
- Create: `frontend-client/src/charla/legal.js`
- Modify: `frontend-client/src/charla/CharlaForm.jsx`, `frontend-client/src/charla/CharlaLanding.jsx`, `frontend-client/src/charla/charla.css`

- [ ] **Step 1: Añadir la dependencia `qrcode.react`**

In `frontend-client/package.json`, en `"dependencies"`, añadí la línea (manteniendo el orden alfabético/JSON válido):

```json
    "qrcode.react": "^3.1.0",
```

Resultado del bloque `dependencies` esperado:

```json
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.26.0",
    "qrcode.react": "^3.1.0",
    "@auditbrain/shared": "file:../frontend-shared"
  },
```

Luego instalá:

```bash
cd frontend-client && npm install
```

Expected: instala `qrcode.react` sin errores.

- [ ] **Step 2: Crear el texto legal del frontend**

Create `frontend-client/src/charla/legal.js`:

```javascript
export const DATA_PROTECTION_CONTACT = "info@auditconsulting.ec";

export const DATA_PROTECTION_TEXT =
  "Audit Consulting Group trata tus datos (nombre, correo, teléfono, identificación, " +
  "empresa) para gestionar tu inscripción y enviarte información de la charla, conforme " +
  "a la Ley Orgánica de Protección de Datos Personales del Ecuador. Podés ejercer tus " +
  `derechos de acceso, rectificación y eliminación escribiendo a ${DATA_PROTECTION_CONTACT}.`;
```

- [ ] **Step 3: Añadir el texto legal bajo el formulario**

In `frontend-client/src/charla/CharlaForm.jsx`:

(a) Añadí el import (después de `import { registrarCharla } from "../api.js";`):

```javascript
import { DATA_PROTECTION_TEXT } from "./legal.js";
```

(b) Justo después del `<button className="charla-btn" ...>...</button>` y antes del cierre `</form>`, añadí:

```jsx
        <p className="charla-legal">{DATA_PROTECTION_TEXT}</p>
```

(El `onSuccess(res)` ya pasa la respuesta del backend hacia arriba; no se cambia.)

- [ ] **Step 4: Reescribir `CharlaLanding.jsx` con la segunda pantalla del QR**

Reemplazá TODO el contenido de `frontend-client/src/charla/CharlaLanding.jsx` por:

```jsx
import { useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import CharlaForm from "./CharlaForm.jsx";
import { DATA_PROTECTION_TEXT } from "./legal.js";
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

function Exito({ evento, resultado }) {
  const grupo = resultado?.whatsapp_group_url || "";
  return (
    <div className="charla-card">
      <div className="charla-success">
        <div className="check">✓</div>
        <h3>¡Inscripción confirmada!</h3>
        {grupo ? (
          <>
            <p>Escaneá este código para unirte al grupo de WhatsApp donde recibirás el link de la charla.</p>
            <div className="charla-qr">
              <QRCodeSVG value={grupo} size={200} level="M" includeMargin />
            </div>
            <a
              className="charla-btn"
              href={grupo}
              target="_blank"
              rel="noopener noreferrer"
              style={{ display: "inline-block", textDecoration: "none", marginTop: 8 }}
            >
              Unirme al grupo
            </a>
          </>
        ) : (
          <p>Pronto te enviaremos el link del grupo de WhatsApp por email.</p>
        )}
        <div className="charla-meta" style={{ justifyContent: "center", marginTop: 16 }}>
          <div><span>Fecha</span><b>{evento.fecha}</b></div>
          <div><span>Hora</span><b>{evento.hora}</b></div>
          <div><span>Modalidad</span><b>{evento.modalidad}</b></div>
        </div>
        <p className="charla-legal">{DATA_PROTECTION_TEXT}</p>
      </div>
    </div>
  );
}

export default function CharlaLanding() {
  const [resultado, setResultado] = useState(null);

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
          {resultado
            ? <Exito evento={EVENTO} resultado={resultado} />
            : <CharlaForm evento={EVENTO} onSuccess={(res) => setResultado(res)} />}
        </div>
        <div className="charla-foot">
          © {new Date().getFullYear()} Audit Consulting Group · Powered by Audit-IA
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Añadir estilos de QR y texto legal**

Al final de `frontend-client/src/charla/charla.css`, añadí:

```css
.charla-qr { display:flex; justify-content:center; margin:16px 0; background:#fff; padding:12px; border-radius:12px; }
.charla-legal { font-size:11px; color:#64748b; line-height:1.5; margin:14px 0 0; border-top:1px solid #e2e8f0; padding-top:12px; }
```

- [ ] **Step 6: Verificar el build**

Run: `cd frontend-client && npm run build`
Expected: build OK, sin errores. El bundle ahora incluye `qrcode.react`.

- [ ] **Step 7: Commit**

```bash
git add frontend-client/package.json frontend-client/package-lock.json frontend-client/src/charla/legal.js frontend-client/src/charla/CharlaForm.jsx frontend-client/src/charla/CharlaLanding.jsx frontend-client/src/charla/charla.css
git commit -m "feat(frontend-client): segunda pantalla con QR al grupo de WhatsApp + texto LOPDP"
```

---

## Task 5: Verificación empírica final

**Files:** ninguno.

- [ ] **Step 1: Suite completa del módulo events + notifications**

Run:
```bash
python -m pytest tests/test_events_catalog.py tests/test_events_models.py tests/test_events_schemas.py tests/test_events_service.py tests/test_events_legal.py tests/test_notifications_charla_email.py tests/test_events_notify.py tests/test_events_router.py -v
```
Expected: TODOS en verde. Reportar conteo. (Nota: ya NO existe `tests/test_notifications_whatsapp.py`.)

- [ ] **Step 2: Confirmar que no se rompió la suite existente**

Run: `python -m pytest tests/ -q --tb=line`
Expected: solo los 5 fallos legacy preexistentes (`test_chat`, 3× `test_context`, `test_sandbox`). Nada nuevo roto.

- [ ] **Step 3: E2E HTTP con grupo configurado**

Run:
```bash
CHARLA_WHATSAPP_GROUP_URL=https://chat.whatsapp.com/TEST123 python - <<'PY'
import uuid
from fastapi.testclient import TestClient
import importlib
import backend.app.events.catalog as cat
importlib.reload(cat)  # re-lee la env var
import app as legacy_app
from backend.app.db.session import init_db
init_db()
with TestClient(legacy_app.app) as c:
    r = c.post("/api/v1/events/charla-anexos-2026-06/registrations", json={
        "nombre": "QR Tester", "email": f"qr-{uuid.uuid4().hex[:6]}@x.ec",
        "telefono": "0987654321", "telefono_pais": "+593",
        "documento": "1791240154001", "empresa": "X S.A.",
    })
    print("status:", r.status_code)
    print("group_url en respuesta:", r.json().get("whatsapp_group_url"))
PY
```
Expected: `status: 201` y `group_url en respuesta: https://chat.whatsapp.com/TEST123`.

> Nota Windows: si el shell no acepta `VAR=val cmd` inline, exportar primero con `set CHARLA_WHATSAPP_GROUP_URL=...` (cmd) o `$env:CHARLA_WHATSAPP_GROUP_URL="..."` (PowerShell) y luego correr `python - <<...`. El `importlib.reload(cat)` asegura que el catálogo lea la env var seteada.

- [ ] **Step 4: Build final del frontend**

Run: `cd frontend-client && npm run build`
Expected: OK.

- [ ] **Step 5: Commit de cierre (si hubo ajustes)**

Si los pasos anteriores no requirieron cambios, no hay nada que commitear. Si hubo correcciones, commitear con `git add` dirigido y mensaje descriptivo.

---

## Self-Review (cobertura del spec — Enmienda v2)

| Requisito (enmienda v2) | Task |
|---|---|
| E1. Eliminar WhatsApp Cloud API (módulo, test, uso, columna, env vars) | Task 1 |
| E2. `whatsapp_group_url` en catálogo (env) + devuelto en respuesta | Task 2 |
| E3. Segunda pantalla con QR + botón respaldo + fallback sin URL | Task 4 |
| E4. Email con botón "Unirme al grupo" + texto legal | Task 3 |
| E5. Texto de protección de datos (form, pantalla QR, email), sin checkbox, contacto configurable | Task 2 (helper backend), Task 3 (email), Task 4 (form + pantalla) |
| E6. Env vars actualizadas | Task 2 (`CHARLA_WHATSAPP_GROUP_URL`), Task 1 (notify lee `DATA_PROTECTION_CONTACT_EMAIL`) |
| E7. Tests afectados actualizados | Tasks 1, 2, 3 |

**Placeholder scan:** sin "TBD"/"TODO"; todo paso de código trae el código real.

**Consistencia de tipos/nombres:** `send_charla_confirmacion(..., whatsapp_group_url=, data_protection_contact=)` definido en Task 3 y llamado idéntico en Task 1 (notify). `RegistrationResponse.whatsapp_group_url` definido en Task 2 y leído en el frontend (Task 4) como `resultado.whatsapp_group_url`. `EventInfo.whatsapp_group_url` definido en Task 2 y usado en notify (Task 1) y router (Task 2). `data_protection_text(contacto)` definido en Task 2 y usado en email (Task 3). El texto legal del frontend (`legal.js`) es copia paralela del backend (intencional: el front no lee env vars del server).

> **Orden de ejecución:** las Tasks 1→2→3 dejan el backend consistente. Entre Task 1 y Task 3 el `notify.py` invoca `send_charla_confirmacion` con kwargs que aún no existen en la firma real, pero esa ruta solo se ejercita con envío real (no en los tests con monkeypatch). Tras la Task 3 todo queda consistente. Ejecutar en orden.
