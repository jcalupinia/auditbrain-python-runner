# Portal Cliente Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the AuditBrain Client Portal MVP — a separate web frontend at `auditbrain-clientes.onrender.com` where external clients log in with strict security (device binding + single active session), browse a categorized catalog of automation tools, upload documents, and download generated deliverables with 24h auto-deletion.

**Architecture:** Shared FastAPI backend (extension of existing AuditBrain) + 2 separated Vite frontends (`frontend/` existing for staff + new `frontend-client/`). Reuses the proven `obligaciones_fiscales` job pattern (`ToolJob` model, `/tmp` storage, `BackgroundTasks` worker, cleanup cron). Three security layers on `/client/*` endpoints: JWT role check, device cookie validation, session uniqueness (sid claim).

**Tech Stack:** FastAPI · SQLAlchemy 2.0 · PyJWT · bcrypt · React 18 · Vite · Resend (email) · pytest · Playwright (E2E) · Render (deploy)

**Out of scope:** The actual ICT 2025 tool logic and NIIF tools go in separate specs/plans. This plan delivers only the portal shell with one "stub" tool registered to validate the end-to-end pipeline.

---

## File Structure (locked in)

### Backend additions
```
backend/app/
├── auth/
│   ├── models.py                ← MODIFY (add Role.client + User columns + ClientDevice)
│   ├── deps.py                  ← MODIFY (add require_client_with_device)
│   ├── jwt_tokens.py            ← MODIFY (accept extra claims sid, did)
│   ├── device.py                ← NEW (fingerprint + device helpers)
│   └── service.py               ← MODIFY (start_session, invalidate_session)
│
├── client_portal/               ← NEW MODULE
│   ├── __init__.py
│   ├── router.py                ← /api/v1/client/* endpoints
│   ├── service.py               ← business logic
│   ├── schemas.py               ← Pydantic models
│   ├── tool_registry.py         ← TOOLS dict (registry pattern)
│   ├── jobs.py                  ← process_tool_job dispatcher
│   └── rate_limit.py            ← in-memory rate limiter for login
│
├── staff_portal/                ← NEW MODULE
│   ├── __init__.py
│   ├── router.py                ← /api/v1/staff/clients/{id}/* endpoints
│   └── service.py
│
├── notifications/               ← NEW MODULE
│   ├── __init__.py
│   ├── email.py                 ← Resend wrapper + retry
│   └── templates/
│       └── job_ready.html
│
├── aud/obligaciones_fiscales/
│   ├── models.py                ← MODIFY (add initiated_from + notify_email to ToolJob)
│   └── cleanup.py               ← MODIFY (add zombie job detector)
│
└── api/router.py                ← MODIFY (register new routers)
```

### Frontend additions
```
frontend-shared/                 ← NEW workspace package
├── package.json                 ← name: "@auditbrain/shared"
└── src/
    ├── Button.jsx
    ├── Input.jsx
    ├── Modal.jsx
    ├── ProgressBar.jsx
    └── index.js

frontend-client/                 ← NEW Vite project
├── package.json                 ← deps: react, react-router-dom, @auditbrain/shared
├── vite.config.js
├── index.html
├── public/assets/logo-auditconsulting-group.png
└── src/
    ├── main.jsx
    ├── App.jsx                  ← Router with public/protected routes
    ├── api.js                   ← fetch wrapper with credentials: 'include'
    ├── auth/
    │   ├── AuthProvider.jsx
    │   ├── Login.jsx
    │   ├── ChangePassword.jsx
    │   └── DeviceBlocked.jsx
    ├── landing/
    │   ├── Landing.jsx
    │   ├── Hero.jsx
    │   ├── Features.jsx
    │   └── CTAs.jsx
    ├── catalog/
    │   ├── ClientCatalog.jsx
    │   └── catalog.css
    ├── tools/
    │   ├── ToolShell.jsx
    │   ├── JobProgress.jsx
    │   └── JobHistory.jsx
    └── shared/
        ├── SessionExpiredModal.jsx
        └── usePolling.js
```

### Tests
```
tests/
├── test_auth_device.py          ← NEW (fingerprint, device validation)
├── test_auth_session.py         ← NEW (sid generation, invalidation)
├── test_client_portal_login.py  ← NEW
├── test_client_portal_jobs.py   ← NEW
├── test_client_isolation.py     ← NEW (CRITICAL: client A vs client B)
├── test_staff_client_admin.py   ← NEW
├── test_notifications_email.py  ← NEW
└── test_zombie_cleanup.py       ← NEW
```

### Deploy
```
render.yaml                      ← MODIFY (add 2nd static site service)
```

---

# PHASE 1 — Backend Data Layer

## Task 1: Extend Role enum + User model

**Files:**
- Modify: `backend/app/auth/models.py`
- Test: `tests/test_auth_session.py` (new file)

- [ ] **Step 1: Write the failing test**

Create `tests/test_auth_session.py`:

```python
"""Tests for new User columns and Role.client enum."""
from backend.app.auth.models import Role, User


def test_role_client_exists():
    assert Role.client.value == "client"


def test_user_has_new_columns(client):
    # Smoke test: User model has the new columns we added
    cols = {c.name for c in User.__table__.columns}
    assert "client_id" in cols
    assert "password_reset_required" in cols
    assert "current_session_id" in cols
    assert "session_started_at" in cols
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_auth_session.py -v
```
Expected: FAIL — `Role.client` does not exist.

- [ ] **Step 3: Modify `backend/app/auth/models.py`**

Replace existing `Role` enum and `User` class:

```python
"""Modelo de usuario y roles."""

import datetime
import enum

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.session import Base


class Role(str, enum.Enum):
    admin = "admin"
    user = "user"
    client = "client"  # Portal cliente externo


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(
        Enum(Role, native_enum=False), default=Role.user, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False
    )
    organization_id: Mapped[int | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    active_project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    # Portal cliente (M2)
    client_id: Mapped[int | None] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"), nullable=True, index=True
    )
    password_reset_required: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    current_session_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    session_started_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime, nullable=True
    )
```

- [ ] **Step 4: Add idempotent ALTER TABLE in `backend/app/db/session.py::init_db`**

Find the section that does `ALTER TABLE users ADD COLUMN organization_id` and add after it:

```python
    # Portal cliente (M2): nuevas columnas en users
    existing_cols = {c["name"] for c in inspector.get_columns("users")}
    for col_def in [
        ("client_id", "INTEGER"),
        ("password_reset_required", "BOOLEAN DEFAULT 0 NOT NULL"),
        ("current_session_id", "VARCHAR(64)"),
        ("session_started_at", "DATETIME"),
    ]:
        col_name, col_type = col_def
        if col_name not in existing_cols:
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}"))
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_auth_session.py -v
```
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/auth/models.py backend/app/db/session.py tests/test_auth_session.py
git commit -m "feat(auth): add Role.client + portal-cliente columns to User"
```

---

## Task 2: Create ClientDevice model

**Files:**
- Modify: `backend/app/auth/models.py`
- Modify: `backend/app/db/session.py` (register model in init_db imports)
- Test: `tests/test_auth_device.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_auth_device.py`:

```python
"""Tests for ClientDevice model."""
from backend.app.auth.models import ClientDevice


def test_client_device_model_exists():
    cols = {c.name for c in ClientDevice.__table__.columns}
    assert "user_id" in cols
    assert "device_id" in cols
    assert "fingerprint_hash" in cols
    assert "is_active" in cols
    assert "revoked_at" in cols
    assert "revoked_by_user_id" in cols
```

- [ ] **Step 2: Run test**

```bash
pytest tests/test_auth_device.py -v
```
Expected: FAIL — `ClientDevice` does not exist.

- [ ] **Step 3: Append `ClientDevice` to `backend/app/auth/models.py`**

```python
class ClientDevice(Base):
    """Vinculación cliente-dispositivo (capa 2 de seguridad del portal)."""

    __tablename__ = "client_devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    device_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    fingerprint_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ip_first_seen: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    registered_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    last_seen_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
```

- [ ] **Step 4: Run test**

```bash
pytest tests/test_auth_device.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/auth/models.py tests/test_auth_device.py
git commit -m "feat(auth): add ClientDevice model for device binding"
```

---

## Task 3: Extend ToolJob model

**Files:**
- Modify: `backend/app/aud/obligaciones_fiscales/models.py`
- Modify: `backend/app/db/session.py` (idempotent ALTER)
- Test: `tests/test_aud_of_models.py` (extend existing)

- [ ] **Step 1: Add test cases to `tests/test_aud_of_models.py`**

Append at end of file:

```python
def test_tool_job_has_new_portal_columns():
    from backend.app.aud.obligaciones_fiscales.models import ToolJob
    cols = {c.name for c in ToolJob.__table__.columns}
    assert "initiated_from" in cols
    assert "notify_email" in cols
```

- [ ] **Step 2: Run**

```bash
pytest tests/test_aud_of_models.py::test_tool_job_has_new_portal_columns -v
```
Expected: FAIL

- [ ] **Step 3: Add columns in `backend/app/aud/obligaciones_fiscales/models.py`**

Inside `ToolJob` class, add:

```python
    # Portal cliente (M2)
    initiated_from: Mapped[str] = mapped_column(
        String(16), default="staff", nullable=False
    )
    notify_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
```

- [ ] **Step 4: Add ALTER TABLE in `backend/app/db/session.py::init_db`**

Find the existing `tool_jobs` ALTER block (firma_auditora) and extend:

```python
    if "tool_jobs" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("tool_jobs")}
        for col_def in [
            ("firma_auditora", "VARCHAR(32)"),
            ("initiated_from", "VARCHAR(16) DEFAULT 'staff' NOT NULL"),
            ("notify_email", "VARCHAR(320)"),
        ]:
            col_name, col_type = col_def
            if col_name not in existing_cols:
                with engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE tool_jobs ADD COLUMN {col_name} {col_type}"))
```

- [ ] **Step 5: Run + commit**

```bash
pytest tests/test_aud_of_models.py -v
git add backend/app/aud/obligaciones_fiscales/models.py backend/app/db/session.py tests/test_aud_of_models.py
git commit -m "feat(aud/of): extend ToolJob with portal cliente columns"
```

---

# PHASE 2 — JWT extension + Device helpers

## Task 4: Extend JWT to accept extra claims (sid, did)

**Files:**
- Modify: `backend/app/auth/jwt_tokens.py`
- Test: `tests/test_auth_session.py` (extend)

- [ ] **Step 1: Add tests**

Append to `tests/test_auth_session.py`:

```python
from backend.app.auth.jwt_tokens import create_access_token, decode_token


def test_jwt_carries_sid_and_did():
    token = create_access_token(
        subject="cliente@example.com",
        role="client",
        extra_claims={"sid": "abc123", "did": "device-xyz"},
    )
    payload = decode_token(token)
    assert payload["sub"] == "cliente@example.com"
    assert payload["role"] == "client"
    assert payload["sid"] == "abc123"
    assert payload["did"] == "device-xyz"


def test_jwt_backward_compatible_without_extra_claims():
    # Old call signature still works for existing staff login
    token = create_access_token(subject="admin@example.com", role="admin")
    payload = decode_token(token)
    assert payload["sub"] == "admin@example.com"
    assert "sid" not in payload
```

- [ ] **Step 2: Run**

```bash
pytest tests/test_auth_session.py -v
```
Expected: FAIL — `extra_claims` parameter not accepted.

- [ ] **Step 3: Modify `backend/app/auth/jwt_tokens.py`**

Replace `create_access_token`:

```python
def create_access_token(
    subject: str, role: str, extra_claims: dict | None = None
) -> str:
    now = datetime.datetime.utcnow()
    payload = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": now + datetime.timedelta(minutes=_ACCESS_TTL_MIN),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, _secret(), algorithm=_ALGO)
```

- [ ] **Step 4: Run + commit**

```bash
pytest tests/test_auth_session.py -v
git add backend/app/auth/jwt_tokens.py tests/test_auth_session.py
git commit -m "feat(auth): JWT accepts extra claims (sid, did) for client portal"
```

---

## Task 5: Create `auth/device.py` module

**Files:**
- Create: `backend/app/auth/device.py`
- Test: `tests/test_auth_device.py` (extend)

- [ ] **Step 1: Add tests**

Append to `tests/test_auth_device.py`:

```python
from backend.app.auth.device import (
    generate_device_id,
    compute_fingerprint_hash,
    register_device,
    validate_device,
    revoke_device,
)


def test_generate_device_id_unique():
    a = generate_device_id()
    b = generate_device_id()
    assert a != b
    assert len(a) == 36  # UUID4 string


def test_fingerprint_hash_deterministic():
    h1 = compute_fingerprint_hash(
        user_agent="Mozilla/5.0 Chrome/120",
        accept_language="en-US",
        accept_encoding="gzip",
    )
    h2 = compute_fingerprint_hash(
        user_agent="Mozilla/5.0 Chrome/120",
        accept_language="en-US",
        accept_encoding="gzip",
    )
    assert h1 == h2
    assert len(h1) == 64  # sha256 hex


def test_fingerprint_hash_changes_with_input():
    h1 = compute_fingerprint_hash(user_agent="Firefox", accept_language="en")
    h2 = compute_fingerprint_hash(user_agent="Chrome", accept_language="en")
    assert h1 != h2
```

- [ ] **Step 2: Run** → FAIL (module not exists)

```bash
pytest tests/test_auth_device.py -v
```

- [ ] **Step 3: Create `backend/app/auth/device.py`**

```python
"""Helpers para vinculación dispositivo-cliente (capa 2 de seguridad)."""

from __future__ import annotations

import datetime
import hashlib
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.auth.models import ClientDevice, User


def generate_device_id() -> str:
    """Genera UUID4 string para identificar dispositivo en cookie."""
    return str(uuid.uuid4())


def compute_fingerprint_hash(
    user_agent: str = "",
    accept_language: str = "",
    accept_encoding: str = "",
) -> str:
    """Hash determinístico del navegador para segunda capa de validación."""
    raw = f"{user_agent}|{accept_language}|{accept_encoding}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def register_device(
    db: Session,
    *,
    user: User,
    fingerprint_hash: str,
    user_agent: str | None = None,
    ip: str | None = None,
) -> ClientDevice:
    """Crea ClientDevice nuevo para el usuario. Devuelve la instancia."""
    now = datetime.datetime.utcnow()
    device = ClientDevice(
        user_id=user.id,
        device_id=generate_device_id(),
        fingerprint_hash=fingerprint_hash,
        user_agent=user_agent,
        ip_first_seen=ip,
        is_active=True,
        registered_at=now,
        last_seen_at=now,
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


def validate_device(
    db: Session,
    *,
    user: User,
    device_id: str,
    fingerprint_hash: str,
) -> ClientDevice | None:
    """Devuelve ClientDevice si es válido (activo, dueño, fingerprint coincide).
    Devuelve None si cualquier validación falla.
    """
    device = db.execute(
        select(ClientDevice).where(ClientDevice.device_id == device_id)
    ).scalar_one_or_none()
    if device is None:
        return None
    if device.user_id != user.id:
        return None
    if not device.is_active:
        return None
    if device.fingerprint_hash != fingerprint_hash:
        return None
    # Touch last_seen
    device.last_seen_at = datetime.datetime.utcnow()
    db.add(device)
    db.commit()
    return device


def revoke_device(
    db: Session, *, device: ClientDevice, revoked_by: User
) -> None:
    """Marca el dispositivo como revocado (no se borra para auditoría)."""
    device.is_active = False
    device.revoked_at = datetime.datetime.utcnow()
    device.revoked_by_user_id = revoked_by.id
    db.add(device)
    db.commit()


def revoke_all_devices_for_user(
    db: Session, *, user: User, revoked_by: User
) -> int:
    """Revoca todos los dispositivos activos del usuario. Retorna count."""
    devices = db.execute(
        select(ClientDevice).where(
            ClientDevice.user_id == user.id,
            ClientDevice.is_active.is_(True),
        )
    ).scalars().all()
    now = datetime.datetime.utcnow()
    for d in devices:
        d.is_active = False
        d.revoked_at = now
        d.revoked_by_user_id = revoked_by.id
        db.add(d)
    db.commit()
    return len(devices)
```

- [ ] **Step 4: Run + commit**

```bash
pytest tests/test_auth_device.py -v
git add backend/app/auth/device.py tests/test_auth_device.py
git commit -m "feat(auth): device fingerprint + register/validate/revoke helpers"
```

---

# PHASE 3 — Session management + service layer

## Task 6: Add session management to `auth/service.py`

**Files:**
- Modify: `backend/app/auth/service.py`
- Test: `tests/test_auth_session.py` (extend)

- [ ] **Step 1: Add tests**

Append to `tests/test_auth_session.py`:

```python
import pytest
from backend.app.auth.service import (
    start_new_session,
    invalidate_session,
    create_user,
)
from backend.app.auth.models import Role
from backend.app.db.session import SessionLocal


@pytest.fixture()
def db_session():
    db = SessionLocal()
    yield db
    db.close()


def test_start_new_session_assigns_sid(db_session):
    u = create_user(db_session, email="t1@x.com", password="pwd123!", role=Role.client)
    sid = start_new_session(db_session, user=u)
    db_session.refresh(u)
    assert u.current_session_id == sid
    assert u.session_started_at is not None
    assert len(sid) == 36  # UUID4


def test_second_session_replaces_first(db_session):
    u = create_user(db_session, email="t2@x.com", password="pwd123!", role=Role.client)
    sid_a = start_new_session(db_session, user=u)
    sid_b = start_new_session(db_session, user=u)
    db_session.refresh(u)
    assert sid_b != sid_a
    assert u.current_session_id == sid_b


def test_invalidate_session_clears_sid(db_session):
    u = create_user(db_session, email="t3@x.com", password="pwd123!", role=Role.client)
    start_new_session(db_session, user=u)
    invalidate_session(db_session, user=u)
    db_session.refresh(u)
    assert u.current_session_id is None
```

- [ ] **Step 2: Run** → FAIL

- [ ] **Step 3: Append to `backend/app/auth/service.py`**

```python
import datetime
import uuid


def start_new_session(db: Session, *, user: User) -> str:
    """Genera nuevo session_id, lo guarda en User, retorna el sid.
    Invalida cualquier sesión anterior (last-login-wins).
    """
    sid = str(uuid.uuid4())
    user.current_session_id = sid
    user.session_started_at = datetime.datetime.utcnow()
    db.add(user)
    db.commit()
    return sid


def invalidate_session(db: Session, *, user: User) -> None:
    """Limpia el session_id activo (logout o force-logout admin)."""
    user.current_session_id = None
    user.session_started_at = None
    db.add(user)
    db.commit()
```

- [ ] **Step 4: Run + commit**

```bash
pytest tests/test_auth_session.py -v
git add backend/app/auth/service.py tests/test_auth_session.py
git commit -m "feat(auth): session management (start/invalidate) for single-active-session"
```

---

# PHASE 4 — Dependencies / Guards

## Task 7: Create `require_client_with_device` dependency

**Files:**
- Modify: `backend/app/auth/deps.py`
- Test: `tests/test_client_portal_login.py` (new)

- [ ] **Step 1: Write integration test scaffold**

Create `tests/test_client_portal_login.py`:

```python
"""Tests for client portal login + 3-layer security guard."""
import pytest
from backend.app.auth.models import Role
from backend.app.auth.service import create_user
from backend.app.auth import device as device_mod
from backend.app.db.session import SessionLocal


@pytest.fixture()
def db_session():
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture()
def client_user(db_session):
    return create_user(
        db_session, email="cliente@example.com", password="ClientPass1!",
        role=Role.client,
    )


def test_guard_rejects_when_role_is_not_client(client, client_user, db_session):
    # Create a staff user and try to access /client/* with it
    from backend.app.auth.jwt_tokens import create_access_token
    token = create_access_token(subject=client_user.email, role="admin")
    # Even with rol=admin in JWT but trying to use /client/* → 403
    r = client.get(
        "/api/v1/client/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403
```

- [ ] **Step 2: Run** → FAIL (endpoint doesn't exist yet — that's OK, we'll add it in Task 9)

- [ ] **Step 3: Modify `backend/app/auth/deps.py`**

Append at end of file:

```python
from fastapi import Cookie

from backend.app.auth.device import compute_fingerprint_hash, validate_device


CLIENT_SESSION_INVALIDATED_CODE = "session_invalidated"
CLIENT_DEVICE_UNAUTHORIZED_CODE = "device_unauthorized"


def require_client_with_device(
    request: Request,
    device_id: str | None = Cookie(default=None, alias="device_id"),
    db: Session = Depends(get_db),
) -> User:
    """Triple validación para endpoints /client/*:
    1. JWT firmado válido + rol == client
    2. Cookie device_id presente, activa, fingerprint coincide
    3. JWT.sid == User.current_session_id (sesión única)
    """
    authz = request.headers.get("Authorization", "")
    if not authz.lower().startswith("bearer "):
        raise HTTPException(401, detail="Falta token Bearer.")
    token = authz.split(" ", 1)[1].strip()

    try:
        payload = decode_token(token)
    except jwt.PyJWTError:
        raise _CRED_EXC

    email = payload.get("sub")
    jwt_role = payload.get("role")
    jwt_sid = payload.get("sid")

    if jwt_role != Role.client.value:
        raise HTTPException(403, detail="Acceso reservado a clientes.")

    user = service.get_user_by_email(db, email)
    if not user or not user.is_active or user.role != Role.client:
        raise _CRED_EXC

    # Layer 3: session uniqueness
    if not jwt_sid or jwt_sid != user.current_session_id:
        raise HTTPException(
            401,
            detail={
                "code": CLIENT_SESSION_INVALIDATED_CODE,
                "message": "Su sesión fue cerrada porque inició sesión desde otro lugar.",
            },
        )

    # Layer 2: device binding
    if not device_id:
        raise HTTPException(
            409,
            detail={
                "code": CLIENT_DEVICE_UNAUTHORIZED_CODE,
                "message": "Falta cookie de dispositivo. Inicie sesión nuevamente.",
            },
        )

    fingerprint = compute_fingerprint_hash(
        user_agent=request.headers.get("user-agent", ""),
        accept_language=request.headers.get("accept-language", ""),
        accept_encoding=request.headers.get("accept-encoding", ""),
    )
    device = validate_device(
        db, user=user, device_id=device_id, fingerprint_hash=fingerprint
    )
    if device is None:
        raise HTTPException(
            409,
            detail={
                "code": CLIENT_DEVICE_UNAUTHORIZED_CODE,
                "message": "Este dispositivo no está autorizado. Solicite reseteo a soporte.",
            },
        )

    return user
```

- [ ] **Step 4: Commit (test still fails because endpoint doesn't exist; will pass in Task 9)**

```bash
git add backend/app/auth/deps.py tests/test_client_portal_login.py
git commit -m "feat(auth): require_client_with_device dependency (3 security layers)"
```

---

# PHASE 5 — Client Portal Service Layer

## Task 8: Create `client_portal/service.py`

**Files:**
- Create: `backend/app/client_portal/__init__.py` (empty)
- Create: `backend/app/client_portal/service.py`
- Test: `tests/test_client_portal_login.py` (extend)

- [ ] **Step 1: Add tests**

Append to `tests/test_client_portal_login.py`:

```python
from backend.app.client_portal.service import (
    create_portal_user,
    authenticate_portal_user,
)
from backend.app.context.models import Organization, Client


@pytest.fixture()
def org_and_client(db_session):
    org = Organization(name="ACG", slug="acg", is_active=True)
    db_session.add(org); db_session.commit(); db_session.refresh(org)
    cli = Client(organization_id=org.id, name="ClienteX", is_active=True)
    db_session.add(cli); db_session.commit(); db_session.refresh(cli)
    return org, cli


def test_create_portal_user_returns_temp_password(db_session, org_and_client):
    org, cli = org_and_client
    user, temp_pwd = create_portal_user(
        db_session, client_id=cli.id, email="newclient@example.com"
    )
    assert user.role == Role.client
    assert user.client_id == cli.id
    assert user.password_reset_required is True
    assert user.organization_id == org.id
    assert len(temp_pwd) >= 12  # auto-generated


def test_authenticate_portal_user_with_wrong_password(db_session, org_and_client):
    _, cli = org_and_client
    user, temp_pwd = create_portal_user(
        db_session, client_id=cli.id, email="auth1@example.com"
    )
    assert authenticate_portal_user(db_session, "auth1@example.com", "wrong") is None
    assert authenticate_portal_user(db_session, "auth1@example.com", temp_pwd) == user
```

- [ ] **Step 2: Run** → FAIL

- [ ] **Step 3: Create `backend/app/client_portal/__init__.py`** (empty)

- [ ] **Step 4: Create `backend/app/client_portal/service.py`**

```python
"""Service layer del portal cliente: creación de cuentas, autenticación,
operaciones específicas del rol client.
"""

from __future__ import annotations

import secrets
import string

from sqlalchemy.orm import Session

from backend.app.auth.models import Role, User
from backend.app.auth.password import hash_password, verify_password
from backend.app.context.models import Client


def _generate_temp_password(length: int = 14) -> str:
    """Genera password temporal seguro: 14 chars, mezcla letras/dígitos/símbolos."""
    alphabet = string.ascii_letters + string.digits + "!@#$%&*"
    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(length))
        # Asegurar al menos 1 minúscula, 1 mayúscula, 1 dígito
        if (
            any(c.islower() for c in pwd)
            and any(c.isupper() for c in pwd)
            and any(c.isdigit() for c in pwd)
        ):
            return pwd


def create_portal_user(
    db: Session, *, client_id: int, email: str
) -> tuple[User, str]:
    """Crea cuenta de portal cliente. Devuelve (User, temp_password).
    El temp_password se retorna 1 vez para que el staff lo entregue al cliente.
    Después solo queda hasheado en la DB.
    """
    client = db.get(Client, client_id)
    if client is None:
        raise ValueError(f"Client {client_id} no existe.")

    temp_pwd = _generate_temp_password()
    user = User(
        email=email.lower(),
        hashed_password=hash_password(temp_pwd),
        role=Role.client,
        is_active=True,
        client_id=client.id,
        organization_id=client.organization_id,
        password_reset_required=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user, temp_pwd


def authenticate_portal_user(db: Session, email: str, password: str) -> User | None:
    """Autenticación específica para portal cliente: solo acepta rol=client."""
    from sqlalchemy import select

    user = db.execute(
        select(User).where(User.email == email.lower())
    ).scalar_one_or_none()
    if not user or not user.is_active:
        return None
    if user.role != Role.client:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def change_password(
    db: Session, *, user: User, new_password: str
) -> None:
    """Cambia password del cliente. Limpia el flag password_reset_required."""
    if len(new_password) < 8:
        raise ValueError("La contraseña debe tener al menos 8 caracteres.")
    user.hashed_password = hash_password(new_password)
    user.password_reset_required = False
    db.add(user)
    db.commit()
```

- [ ] **Step 5: Run + commit**

```bash
pytest tests/test_client_portal_login.py::test_create_portal_user_returns_temp_password tests/test_client_portal_login.py::test_authenticate_portal_user_with_wrong_password -v
git add backend/app/client_portal/__init__.py backend/app/client_portal/service.py tests/test_client_portal_login.py
git commit -m "feat(client_portal): service layer for user creation + authentication"
```

---

## Task 9: Create `client_portal/router.py` with auth endpoints

**Files:**
- Create: `backend/app/client_portal/schemas.py`
- Create: `backend/app/client_portal/router.py`
- Modify: `backend/app/api/router.py` (register router)
- Test: `tests/test_client_portal_login.py` (extend)

- [ ] **Step 1: Add tests**

Append to `tests/test_client_portal_login.py`:

```python
def test_first_login_returns_password_reset_required(client, db_session, org_and_client):
    _, cli = org_and_client
    user, temp_pwd = create_portal_user(
        db_session, client_id=cli.id, email="first@example.com"
    )
    r = client.post(
        "/api/v1/client/auth/login",
        data={"username": "first@example.com", "password": temp_pwd},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["password_reset_required"] is True
    assert "access_token" in body
    # Cookie device_id se debe haber seteado
    assert "device_id" in r.cookies


def test_login_with_wrong_credentials_returns_401(client, db_session, org_and_client):
    r = client.post(
        "/api/v1/client/auth/login",
        data={"username": "nobody@example.com", "password": "x"},
    )
    assert r.status_code == 401


def test_change_password_clears_flag(client, db_session, org_and_client):
    _, cli = org_and_client
    user, temp_pwd = create_portal_user(
        db_session, client_id=cli.id, email="cp@example.com"
    )
    # Login
    r = client.post(
        "/api/v1/client/auth/login",
        data={"username": "cp@example.com", "password": temp_pwd},
    )
    token = r.json()["access_token"]
    # Change password
    r2 = client.post(
        "/api/v1/client/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"old_password": temp_pwd, "new_password": "NewSecure123!"},
    )
    assert r2.status_code == 200
    db_session.refresh(user)
    assert user.password_reset_required is False
```

- [ ] **Step 2: Create `backend/app/client_portal/schemas.py`**

```python
"""Schemas Pydantic del portal cliente."""

from pydantic import BaseModel, EmailStr, Field


class ClientLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    password_reset_required: bool


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8)


class ClientMeResponse(BaseModel):
    email: EmailStr
    client_id: int | None
    organization_id: int | None
    password_reset_required: bool
```

- [ ] **Step 3: Create `backend/app/client_portal/router.py`**

```python
"""Endpoints /api/v1/client/* (autenticación + perfil)."""

from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from backend.app.auth import device as device_mod
from backend.app.auth.deps import require_client_with_device
from backend.app.auth.jwt_tokens import create_access_token
from backend.app.auth.models import User
from backend.app.auth.service import start_new_session, invalidate_session
from backend.app.client_portal import service as cp_service
from backend.app.client_portal.schemas import (
    ChangePasswordRequest,
    ClientLoginResponse,
    ClientMeResponse,
)
from backend.app.db.session import get_db

router = APIRouter(prefix="/client", tags=["client-portal"])


@router.post("/auth/login", response_model=ClientLoginResponse)
def client_login(
    request: Request,
    response: Response,
    form: OAuth2PasswordRequestForm = Depends(),
    device_id: str | None = Cookie(default=None, alias="device_id"),
    db: Session = Depends(get_db),
):
    """Login del cliente. Setea cookie device_id (primer login) o valida match.
    Triple seguridad: si device_id no coincide con el guardado → 409.
    """
    user = cp_service.authenticate_portal_user(db, form.username, form.password)
    if not user:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Calcular fingerprint del request actual
    fingerprint = device_mod.compute_fingerprint_hash(
        user_agent=request.headers.get("user-agent", ""),
        accept_language=request.headers.get("accept-language", ""),
        accept_encoding=request.headers.get("accept-encoding", ""),
    )
    ip = request.client.host if request.client else None

    # Si cookie viene, validar device existente; si no, registrar nuevo
    device = None
    if device_id:
        device = device_mod.validate_device(
            db, user=user, device_id=device_id, fingerprint_hash=fingerprint
        )
        if device is None:
            # Cookie existe pero el device no es válido (revocado u otro usuario)
            raise HTTPException(
                409,
                detail={
                    "code": "device_unauthorized",
                    "message": (
                        "Este dispositivo no está autorizado para esta cuenta. "
                        "Solicite reseteo a soporte."
                    ),
                },
            )

    if device is None:
        # Primer login (o sin cookie): registrar dispositivo + setear cookie
        # Política: si el usuario ya tiene devices activos, debe pasar por reset.
        from sqlalchemy import select
        from backend.app.auth.models import ClientDevice
        existing = db.execute(
            select(ClientDevice).where(
                ClientDevice.user_id == user.id,
                ClientDevice.is_active.is_(True),
            )
        ).scalars().first()
        if existing:
            raise HTTPException(
                409,
                detail={
                    "code": "device_unauthorized",
                    "message": (
                        "Ya existe un dispositivo registrado para esta cuenta. "
                        "Solicite reseteo a soporte si cambió de equipo."
                    ),
                },
            )
        device = device_mod.register_device(
            db,
            user=user,
            fingerprint_hash=fingerprint,
            user_agent=request.headers.get("user-agent"),
            ip=ip,
        )
        response.set_cookie(
            key="device_id",
            value=device.device_id,
            max_age=60 * 60 * 24 * 365,  # 1 año
            httponly=True,
            secure=True,
            samesite="strict",
        )

    # Generar nuevo sid → invalida sesión anterior (last-login-wins)
    sid = start_new_session(db, user=user)
    token = create_access_token(
        subject=user.email,
        role=user.role.value,
        extra_claims={"sid": sid, "did": device.device_id},
    )

    return ClientLoginResponse(
        access_token=token,
        password_reset_required=user.password_reset_required,
    )


@router.post("/auth/change-password", status_code=200)
def change_password_endpoint(
    payload: ChangePasswordRequest,
    user: User = Depends(require_client_with_device),
    db: Session = Depends(get_db),
):
    if not cp_service.authenticate_portal_user(db, user.email, payload.old_password):
        raise HTTPException(400, detail="La contraseña actual no coincide.")
    try:
        cp_service.change_password(db, user=user, new_password=payload.new_password)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))
    return {"ok": True}


@router.get("/auth/me", response_model=ClientMeResponse)
def me(user: User = Depends(require_client_with_device)):
    return ClientMeResponse(
        email=user.email,
        client_id=user.client_id,
        organization_id=user.organization_id,
        password_reset_required=user.password_reset_required,
    )


@router.post("/auth/logout", status_code=200)
def logout(
    user: User = Depends(require_client_with_device),
    db: Session = Depends(get_db),
):
    invalidate_session(db, user=user)
    return {"ok": True}
```

- [ ] **Step 4: Register router in `backend/app/api/router.py`**

Find the existing router registration block and add:

```python
from backend.app.client_portal.router import router as client_portal_router
api_router.include_router(client_portal_router)
```

- [ ] **Step 5: Run all client portal login tests**

```bash
pytest tests/test_client_portal_login.py -v
```
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/client_portal/schemas.py backend/app/client_portal/router.py backend/app/api/router.py
git commit -m "feat(client_portal): auth endpoints (login/change-password/me/logout)"
```

---

## Task 10: Session uniqueness E2E test

**Files:**
- Test: `tests/test_client_portal_login.py` (extend)

- [ ] **Step 1: Add critical test**

Append to `tests/test_client_portal_login.py`:

```python
def test_second_login_invalidates_first_session(client, db_session, org_and_client):
    _, cli = org_and_client
    user, temp_pwd = create_portal_user(
        db_session, client_id=cli.id, email="dual@example.com"
    )
    # Login A
    r_a = client.post(
        "/api/v1/client/auth/login",
        data={"username": "dual@example.com", "password": temp_pwd},
    )
    token_a = r_a.json()["access_token"]

    # Login B (mismo cliente, mismo computador → mismo fingerprint OK)
    # En tests TestClient comparte cookies por sesión, simulamos misma máquina
    r_b = client.post(
        "/api/v1/client/auth/login",
        data={"username": "dual@example.com", "password": temp_pwd},
    )
    assert r_b.status_code == 200
    token_b = r_b.json()["access_token"]
    assert token_a != token_b

    # Token A ya no debe funcionar (sid invalidado)
    r_check = client.get(
        "/api/v1/client/auth/me",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert r_check.status_code == 401
    body = r_check.json()
    # El detail puede ser dict o str según FastAPI version
    if isinstance(body.get("detail"), dict):
        assert body["detail"]["code"] == "session_invalidated"
```

- [ ] **Step 2: Run + commit (this validates the full single-session chain)**

```bash
pytest tests/test_client_portal_login.py::test_second_login_invalidates_first_session -v
git add tests/test_client_portal_login.py
git commit -m "test(client_portal): second login invalidates first session (sid)"
```

---

# PHASE 6 — Staff Admin Endpoints

## Task 11: Create `staff_portal/service.py` + initial endpoints

**Files:**
- Create: `backend/app/staff_portal/__init__.py` (empty)
- Create: `backend/app/staff_portal/service.py`
- Create: `backend/app/staff_portal/router.py`
- Modify: `backend/app/api/router.py`
- Test: `tests/test_staff_client_admin.py` (new)

- [ ] **Step 1: Add tests**

Create `tests/test_staff_client_admin.py`:

```python
"""Tests for /api/v1/staff/clients/{id}/portal-users + /devices."""
import pytest
from backend.app.auth.models import Role
from backend.app.auth.service import create_user
from backend.app.auth.jwt_tokens import create_access_token
from backend.app.context.models import Organization, Client
from backend.app.db.session import SessionLocal


@pytest.fixture()
def db_session():
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture()
def admin_token(db_session):
    u = create_user(db_session, email="admin@x.com", password="x", role=Role.admin)
    return create_access_token(subject=u.email, role="admin")


@pytest.fixture()
def org_client(db_session):
    org = Organization(name="ACG", slug="acg-staff", is_active=True)
    db_session.add(org); db_session.commit(); db_session.refresh(org)
    cli = Client(organization_id=org.id, name="CL1", is_active=True)
    db_session.add(cli); db_session.commit(); db_session.refresh(cli)
    return org, cli


def test_admin_creates_portal_user_returns_temp_password(client, admin_token, org_client):
    _, cli = org_client
    r = client.post(
        f"/api/v1/staff/clients/{cli.id}/portal-users",
        json={"email": "newportal@example.com"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "newportal@example.com"
    assert "temp_password" in body
    assert len(body["temp_password"]) >= 12


def test_user_role_cannot_create_portal_users(client, db_session, org_client):
    _, cli = org_client
    u = create_user(db_session, email="staffuser@x.com", password="x", role=Role.user)
    token = create_access_token(subject=u.email, role="user")
    r = client.post(
        f"/api/v1/staff/clients/{cli.id}/portal-users",
        json={"email": "denied@example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403
```

- [ ] **Step 2: Create `backend/app/staff_portal/__init__.py`** (empty)

- [ ] **Step 3: Create `backend/app/staff_portal/service.py`**

```python
"""Service layer del staff portal: gestión de cuentas y dispositivos cliente."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.auth import device as device_mod
from backend.app.auth.models import ClientDevice, Role, User
from backend.app.auth.service import invalidate_session
from backend.app.client_portal.service import create_portal_user


def list_portal_users(db: Session, *, client_id: int) -> list[User]:
    return list(
        db.execute(
            select(User).where(User.client_id == client_id, User.role == Role.client)
        ).scalars()
    )


def disable_portal_user(db: Session, *, user: User) -> None:
    user.is_active = False
    db.add(user)
    db.commit()


def list_devices(db: Session, *, user_id: int) -> list[ClientDevice]:
    return list(
        db.execute(
            select(ClientDevice).where(ClientDevice.user_id == user_id)
            .order_by(ClientDevice.registered_at.desc())
        ).scalars()
    )


def reset_all_devices(db: Session, *, user: User, revoked_by: User) -> int:
    return device_mod.revoke_all_devices_for_user(db, user=user, revoked_by=revoked_by)


def force_logout(db: Session, *, user: User) -> None:
    invalidate_session(db, user=user)
```

- [ ] **Step 4: Create `backend/app/staff_portal/router.py`**

```python
"""Endpoints /api/v1/staff/clients/{id}/* (gestión de cuentas y dispositivos)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from backend.app.auth import device as device_mod
from backend.app.auth.deps import get_current_user, require_admin
from backend.app.auth.models import ClientDevice, Role, User
from backend.app.client_portal import service as cp_service
from backend.app.context.models import Client
from backend.app.db.session import get_db
from backend.app.staff_portal import service as sp_service

router = APIRouter(prefix="/staff/clients", tags=["staff-clients"])


class CreatePortalUserRequest(BaseModel):
    email: EmailStr


class CreatePortalUserResponse(BaseModel):
    user_id: int
    email: str
    temp_password: str
    note: str = "Comparta este password con el cliente por canal seguro. No se vuelve a mostrar."


class PortalUserOut(BaseModel):
    id: int
    email: str
    is_active: bool
    password_reset_required: bool


class DeviceOut(BaseModel):
    id: int
    device_id: str
    user_agent: str | None
    ip_first_seen: str | None
    is_active: bool
    registered_at: str
    last_seen_at: str


@router.post(
    "/{client_id}/portal-users",
    response_model=CreatePortalUserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
def create_portal_user_endpoint(
    client_id: int,
    payload: CreatePortalUserRequest,
    db: Session = Depends(get_db),
):
    if db.get(Client, client_id) is None:
        raise HTTPException(404, detail="Cliente no existe.")
    try:
        user, temp = cp_service.create_portal_user(
            db, client_id=client_id, email=payload.email
        )
    except ValueError as e:
        raise HTTPException(400, detail=str(e))
    return CreatePortalUserResponse(
        user_id=user.id, email=user.email, temp_password=temp
    )


@router.get("/{client_id}/portal-users", response_model=list[PortalUserOut])
def list_portal_users_endpoint(
    client_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),  # admin o user staff
):
    users = sp_service.list_portal_users(db, client_id=client_id)
    return [PortalUserOut(
        id=u.id, email=u.email, is_active=u.is_active,
        password_reset_required=u.password_reset_required,
    ) for u in users]


@router.post(
    "/{client_id}/portal-users/{user_id}/disable",
    status_code=200,
    dependencies=[Depends(require_admin)],
)
def disable_portal_user_endpoint(
    client_id: int, user_id: int, db: Session = Depends(get_db)
):
    user = db.get(User, user_id)
    if user is None or user.client_id != client_id:
        raise HTTPException(404, detail="Usuario no encontrado para este cliente.")
    sp_service.disable_portal_user(db, user=user)
    return {"ok": True}


@router.get("/{client_id}/portal-users/{user_id}/devices", response_model=list[DeviceOut])
def list_devices_endpoint(
    client_id: int, user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    user = db.get(User, user_id)
    if user is None or user.client_id != client_id:
        raise HTTPException(404)
    devices = sp_service.list_devices(db, user_id=user_id)
    return [DeviceOut(
        id=d.id, device_id=d.device_id, user_agent=d.user_agent,
        ip_first_seen=d.ip_first_seen, is_active=d.is_active,
        registered_at=d.registered_at.isoformat(),
        last_seen_at=d.last_seen_at.isoformat(),
    ) for d in devices]


@router.post(
    "/{client_id}/portal-users/{user_id}/reset-device",
    status_code=200,
    dependencies=[Depends(require_admin)],
)
def reset_device_endpoint(
    client_id: int, user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = db.get(User, user_id)
    if user is None or user.client_id != client_id:
        raise HTTPException(404)
    count = sp_service.reset_all_devices(db, user=user, revoked_by=admin)
    return {"ok": True, "devices_revoked": count}


@router.post(
    "/{client_id}/portal-users/{user_id}/force-logout",
    status_code=200,
    dependencies=[Depends(require_admin)],
)
def force_logout_endpoint(
    client_id: int, user_id: int, db: Session = Depends(get_db)
):
    user = db.get(User, user_id)
    if user is None or user.client_id != client_id:
        raise HTTPException(404)
    sp_service.force_logout(db, user=user)
    return {"ok": True}
```

- [ ] **Step 5: Register in `backend/app/api/router.py`**

```python
from backend.app.staff_portal.router import router as staff_clients_router
api_router.include_router(staff_clients_router)
```

- [ ] **Step 6: Run + commit**

```bash
pytest tests/test_staff_client_admin.py -v
git add backend/app/staff_portal/ backend/app/api/router.py tests/test_staff_client_admin.py
git commit -m "feat(staff_portal): admin endpoints to manage client portal users + devices"
```

---

# PHASE 7 — Tool Registry + Catalog

## Task 12: Tool registry + stub tool for testing pipeline

**Files:**
- Create: `backend/app/client_portal/tool_registry.py`

- [ ] **Step 1: Create `backend/app/client_portal/tool_registry.py`**

```python
"""Registry de herramientas del portal cliente.

Cada tool declara:
- code: string único (ej. "STUB_ECHO", "ICT_2025", "NIIF_9_ECL")
- label, description, category (para el catálogo)
- slots: dict de nombre → {mimes_allowed, required, multi}
- processor: callable(job_id) -> None que el worker invoca

Nuevas tools se añaden registrando aquí. El resto del pipeline es agnóstico.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class SlotConfig:
    mimes_allowed: frozenset[str]
    required: bool = True
    multi: bool = False  # True permite múltiples archivos en el slot


@dataclass(frozen=True)
class ToolConfig:
    code: str
    label: str
    description: str
    category: str
    slots: dict[str, SlotConfig]
    processor: Callable[[int], None]
    enabled: bool = True


# Stub processor para validar pipeline end-to-end sin lógica real
def _stub_echo_processor(job_id: int) -> None:
    """Procesador stub: copia el primer input como output.xlsx, marca done."""
    from backend.app.aud.obligaciones_fiscales import file_storage
    from backend.app.aud.obligaciones_fiscales.models import ToolJob
    from backend.app.db.session import SessionLocal

    db = SessionLocal()
    try:
        job = db.get(ToolJob, job_id)
        if job is None:
            return
        job.status = "processing"
        db.commit()

        job_dir = file_storage.job_dir(job_id)
        all_inputs = file_storage.list_inputs(job_dir)
        if not all_inputs:
            job.status = "error"
            job.error_message = "No se encontraron inputs."
            db.commit()
            return

        # Copia byte-a-byte del primer input como output
        out_path = file_storage.output_path(job_dir)
        out_path.write_bytes(all_inputs[0].read_bytes())

        job.status = "done"
        job.summary_json = {"echo_bytes": len(out_path.read_bytes())}
        db.commit()
    finally:
        db.close()


TOOLS: dict[str, ToolConfig] = {
    "STUB_ECHO": ToolConfig(
        code="STUB_ECHO",
        label="Stub Echo (testing)",
        description="Herramienta de prueba: copia el archivo subido como output.",
        category="TESTING",
        slots={
            "input": SlotConfig(
                mimes_allowed=frozenset({"application/pdf", "text/plain"}),
                required=True,
                multi=False,
            ),
        },
        processor=_stub_echo_processor,
        enabled=True,
    ),
}


def get_tool(code: str) -> ToolConfig:
    if code not in TOOLS:
        raise KeyError(f"Tool {code} no está registrada.")
    return TOOLS[code]


def list_enabled_tools() -> list[ToolConfig]:
    return [t for t in TOOLS.values() if t.enabled]


# Categorías para el catálogo (más adelante, herramientas NIIF se añaden aquí)
CATEGORIES = [
    {"id": "CUMPLIMIENTO_TRIBUTARIO", "label": "Cumplimiento Tributario"},
    {"id": "NIIF_CXC", "label": "NIIF - Cuentas por Cobrar"},
    {"id": "NIIF_INVENTARIOS", "label": "NIIF - Inventarios"},
    {"id": "NIIF_ACTIVOS_FIJOS", "label": "NIIF - Activos Fijos"},
    {"id": "NIIF_INGRESOS", "label": "NIIF - Ingresos"},
    {"id": "TESTING", "label": "Pruebas (interno)"},
]
```

- [ ] **Step 2: Test the registry**

Create `tests/test_tool_registry.py`:

```python
from backend.app.client_portal.tool_registry import (
    TOOLS, get_tool, list_enabled_tools, CATEGORIES,
)


def test_stub_tool_registered():
    assert "STUB_ECHO" in TOOLS
    t = get_tool("STUB_ECHO")
    assert t.label == "Stub Echo (testing)"
    assert "input" in t.slots


def test_get_unknown_tool_raises():
    import pytest
    with pytest.raises(KeyError):
        get_tool("DOES_NOT_EXIST")


def test_categories_have_required_keys():
    for cat in CATEGORIES:
        assert "id" in cat
        assert "label" in cat
```

- [ ] **Step 3: Run + commit**

```bash
pytest tests/test_tool_registry.py -v
git add backend/app/client_portal/tool_registry.py tests/test_tool_registry.py
git commit -m "feat(client_portal): tool registry + STUB_ECHO for pipeline testing"
```

---

## Task 13: Catalog endpoint

**Files:**
- Modify: `backend/app/client_portal/router.py`
- Modify: `backend/app/client_portal/schemas.py`
- Test: `tests/test_client_portal_jobs.py` (new)

- [ ] **Step 1: Add schemas**

Append to `backend/app/client_portal/schemas.py`:

```python
from typing import Any


class SlotOut(BaseModel):
    name: str
    mimes_allowed: list[str]
    required: bool
    multi: bool


class ToolOut(BaseModel):
    code: str
    label: str
    description: str
    category: str
    slots: list[SlotOut]


class CategoryOut(BaseModel):
    id: str
    label: str
    tools: list[ToolOut]


class ClientCatalogResponse(BaseModel):
    categories: list[CategoryOut]
```

- [ ] **Step 2: Add tests**

Create `tests/test_client_portal_jobs.py`:

```python
"""Tests for /client/tools/* endpoints (catalog + jobs)."""
import io
import pytest
from backend.app.auth.models import Role
from backend.app.client_portal.service import create_portal_user
from backend.app.context.models import Organization, Client
from backend.app.db.session import SessionLocal


@pytest.fixture()
def db_session():
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture()
def logged_client(client, db_session):
    """Fixture: cliente logueado con device cookie ya seteada."""
    org = Organization(name="ACG-jobs", slug="acg-jobs", is_active=True)
    db_session.add(org); db_session.commit(); db_session.refresh(org)
    cli = Client(organization_id=org.id, name="CL-jobs", is_active=True)
    db_session.add(cli); db_session.commit(); db_session.refresh(cli)
    user, pwd = create_portal_user(
        db_session, client_id=cli.id, email="jobs@example.com"
    )
    r = client.post(
        "/api/v1/client/auth/login",
        data={"username": "jobs@example.com", "password": pwd},
    )
    token = r.json()["access_token"]
    return {"user": user, "token": token, "client": cli, "headers":
            {"Authorization": f"Bearer {token}"}}


def test_catalog_returns_categories_with_stub_tool(client, logged_client):
    r = client.get("/api/v1/client/catalog", headers=logged_client["headers"])
    assert r.status_code == 200
    body = r.json()
    cats = {c["id"]: c for c in body["categories"]}
    assert "TESTING" in cats
    stub_cat = cats["TESTING"]
    tool_codes = [t["code"] for t in stub_cat["tools"]]
    assert "STUB_ECHO" in tool_codes


def test_catalog_rejects_unauthenticated(client):
    r = client.get("/api/v1/client/catalog")
    assert r.status_code in (401, 403)
```

- [ ] **Step 3: Add catalog endpoint to `backend/app/client_portal/router.py`**

Append:

```python
from backend.app.client_portal.tool_registry import CATEGORIES, list_enabled_tools


@router.get("/catalog", response_model=ClientCatalogResponse)
def get_catalog(
    _: User = Depends(require_client_with_device),
):
    """Catálogo de herramientas habilitadas para el cliente.
    Por ahora retorna TODAS las tools habilitadas. Filtrado por organización
    es upgrade futuro (gating comercial).
    """
    tools_by_cat: dict[str, list] = {c["id"]: [] for c in CATEGORIES}
    for t in list_enabled_tools():
        if t.category not in tools_by_cat:
            tools_by_cat[t.category] = []
        slots_out = [
            SlotOut(
                name=name,
                mimes_allowed=sorted(cfg.mimes_allowed),
                required=cfg.required,
                multi=cfg.multi,
            )
            for name, cfg in t.slots.items()
        ]
        tools_by_cat[t.category].append(ToolOut(
            code=t.code, label=t.label, description=t.description,
            category=t.category, slots=slots_out,
        ))
    return ClientCatalogResponse(
        categories=[
            CategoryOut(id=c["id"], label=c["label"], tools=tools_by_cat.get(c["id"], []))
            for c in CATEGORIES
        ]
    )
```

Also add imports at top of router.py: `from backend.app.client_portal.schemas import SlotOut, ToolOut, CategoryOut, ClientCatalogResponse`

- [ ] **Step 4: Run + commit**

```bash
pytest tests/test_client_portal_jobs.py -v
git add backend/app/client_portal/router.py backend/app/client_portal/schemas.py tests/test_client_portal_jobs.py
git commit -m "feat(client_portal): /catalog endpoint returns categories+tools+slots"
```

---

# PHASE 8 — Job Pipeline (Upload → Process → Download)

## Task 14: Job dispatcher + create job endpoint

**Files:**
- Create: `backend/app/client_portal/jobs.py`
- Modify: `backend/app/client_portal/router.py`
- Modify: `backend/app/client_portal/service.py`
- Test: `tests/test_client_portal_jobs.py` (extend)

- [ ] **Step 1: Add test**

Append to `tests/test_client_portal_jobs.py`:

```python
def test_create_stub_job_and_complete(client, logged_client, db_session):
    # Upload a small file
    fake_pdf = b"%PDF-1.4 fake content"
    files = {
        "input": ("test.pdf", io.BytesIO(fake_pdf), "application/pdf"),
    }
    r = client.post(
        "/api/v1/client/tools/STUB_ECHO/jobs",
        files=files,
        headers=logged_client["headers"],
    )
    assert r.status_code == 201
    job_id = r.json()["id"]

    # Poll until done (BackgroundTasks runs synchronously in TestClient)
    r2 = client.get(
        f"/api/v1/client/tools/jobs/{job_id}",
        headers=logged_client["headers"],
    )
    assert r2.status_code == 200
    body = r2.json()
    assert body["status"] == "done"


def test_create_job_with_wrong_mime_rejected(client, logged_client):
    files = {
        "input": ("test.docx", io.BytesIO(b"x"),
                  "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    }
    r = client.post(
        "/api/v1/client/tools/STUB_ECHO/jobs",
        files=files,
        headers=logged_client["headers"],
    )
    assert r.status_code == 415


def test_create_job_with_unknown_tool_returns_404(client, logged_client):
    r = client.post(
        "/api/v1/client/tools/DOES_NOT_EXIST/jobs",
        files={"input": ("x.pdf", io.BytesIO(b"x"), "application/pdf")},
        headers=logged_client["headers"],
    )
    assert r.status_code == 404
```

- [ ] **Step 2: Add to `backend/app/client_portal/service.py`**

```python
import datetime

from backend.app.aud.obligaciones_fiscales.models import ToolJob
from backend.app.core.config import settings


def create_client_job(
    db: Session, *, user: User, tool_code: str
) -> ToolJob:
    """Crea ToolJob para un cliente (sin project_id porque cliente no tiene
    proyectos; se usa client_id directamente).
    """
    # Verificar que cliente no tenga otro job activo
    from sqlalchemy import select
    active = db.execute(
        select(ToolJob).where(
            ToolJob.user_id == user.id,
            ToolJob.status.in_(["pending", "processing"]),
        )
    ).scalars().first()
    if active:
        raise PermissionError(
            "Tiene otro trabajo en proceso. Espere a que termine."
        )

    now = datetime.datetime.utcnow()
    # project_id es required en ToolJob; usamos un proyecto-stub o el active del cliente.
    # Para MVP: si el cliente no tiene active_project_id, lo creamos.
    project_id = _ensure_client_project(db, user=user)

    job = ToolJob(
        user_id=user.id,
        project_id=project_id,
        tool_code=tool_code,
        status="pending",
        cliente_name=str(user.client_id or user.email),
        period_label=datetime.date.today().isoformat(),
        created_at=now,
        expires_at=now + datetime.timedelta(hours=24),
        initiated_from="client",
        notify_email=user.email,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _ensure_client_project(db: Session, *, user: User) -> int:
    """Devuelve project_id "stub" para jobs del cliente. Crea uno si no existe."""
    from backend.app.context.models import Project
    if user.active_project_id:
        return user.active_project_id
    # Crear proyecto stub vinculado a su client_id
    proj = Project(
        organization_id=user.organization_id,
        client_id=user.client_id,
        name=f"PortalCliente-{user.email}",
        module_code="CP",
    )
    db.add(proj); db.commit(); db.refresh(proj)
    user.active_project_id = proj.id
    db.add(user); db.commit()
    return proj.id


def get_client_job(db: Session, *, user: User, job_id: int) -> ToolJob:
    """Obtiene job verificando ownership del cliente."""
    job = db.get(ToolJob, job_id)
    if not job or job.user_id != user.id:
        raise PermissionError("Job no encontrado o sin acceso.")
    return job
```

- [ ] **Step 3: Create `backend/app/client_portal/jobs.py`**

```python
"""Dispatcher genérico que el worker invoca desde BackgroundTasks."""

from __future__ import annotations

import logging

from backend.app.client_portal.tool_registry import get_tool

log = logging.getLogger(__name__)


def process_tool_job(job_id: int) -> None:
    """Lee el job, busca su tool_code en el registry, invoca el processor."""
    from backend.app.aud.obligaciones_fiscales.models import ToolJob
    from backend.app.db.session import SessionLocal

    db = SessionLocal()
    try:
        job = db.get(ToolJob, job_id)
        if job is None:
            log.error("process_tool_job: job %s not found", job_id)
            return
        tool_code = job.tool_code
    finally:
        db.close()

    try:
        tool = get_tool(tool_code)
    except KeyError:
        log.error("process_tool_job: tool %s not registered", tool_code)
        _mark_error(job_id, f"Tool {tool_code} no registrada.")
        return

    try:
        tool.processor(job_id)
    except Exception as e:  # noqa: BLE001
        log.exception("process_tool_job %s failed", job_id)
        _mark_error(job_id, str(e))


def _mark_error(job_id: int, message: str) -> None:
    from backend.app.aud.obligaciones_fiscales.models import ToolJob
    from backend.app.db.session import SessionLocal

    db = SessionLocal()
    try:
        job = db.get(ToolJob, job_id)
        if job is None:
            return
        job.status = "error"
        job.error_message = message
        db.commit()
    finally:
        db.close()
```

- [ ] **Step 4: Add endpoints to `backend/app/client_portal/router.py`**

Add at top imports:

```python
from fastapi import BackgroundTasks, File, UploadFile
from fastapi.responses import StreamingResponse
from io import BytesIO

from backend.app.aud.obligaciones_fiscales import file_storage
from backend.app.aud.obligaciones_fiscales.schemas import JobOut
from backend.app.client_portal import jobs as cp_jobs
from backend.app.client_portal.tool_registry import get_tool
```

Append endpoints:

```python
MAX_FILE_BYTES = 50 * 1024 * 1024  # 50 MB per file


@router.post(
    "/tools/{tool_code}/jobs",
    response_model=JobOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_client_job_endpoint(
    tool_code: str,
    background_tasks: BackgroundTasks,
    request: Request,
    user: User = Depends(require_client_with_device),
    db: Session = Depends(get_db),
):
    """Recibe multipart con un campo de archivo por slot.
    Valida MIMEs según el tool registrado, guarda en /tmp, crea ToolJob,
    lanza BackgroundTask.
    """
    try:
        tool = get_tool(tool_code)
    except KeyError:
        raise HTTPException(404, detail=f"Tool {tool_code} no existe.")

    # Parsear multipart manualmente para soportar slots dinámicos
    form = await request.form()

    # Validar cada slot
    files_by_slot: dict[str, list[UploadFile]] = {}
    for slot_name, slot_cfg in tool.slots.items():
        items = form.getlist(slot_name)
        upload_files = [f for f in items if isinstance(f, UploadFile)]
        if slot_cfg.required and not upload_files:
            raise HTTPException(
                400, detail=f"Falta archivo obligatorio para slot '{slot_name}'."
            )
        for f in upload_files:
            if f.content_type not in slot_cfg.mimes_allowed:
                raise HTTPException(
                    415,
                    detail=(
                        f"Slot '{slot_name}': MIME '{f.content_type}' no permitido. "
                        f"Esperado: {sorted(slot_cfg.mimes_allowed)}"
                    ),
                )
        if not slot_cfg.multi and len(upload_files) > 1:
            raise HTTPException(
                400, detail=f"Slot '{slot_name}' acepta máximo 1 archivo."
            )
        files_by_slot[slot_name] = upload_files

    # Crear job (verifica que no haya otro activo)
    try:
        job = cp_service.create_client_job(db, user=user, tool_code=tool_code)
    except PermissionError as e:
        raise HTTPException(409, detail=str(e))

    # Guardar archivos
    job_dir = file_storage.create_job_dir(job.id)
    try:
        for slot_name, files in files_by_slot.items():
            for f in files:
                data = await f.read()
                if len(data) > MAX_FILE_BYTES:
                    raise HTTPException(
                        413,
                        detail=f"Archivo {f.filename} excede {MAX_FILE_BYTES // (1024*1024)} MB",
                    )
                file_storage.save_input(job_dir, slot_name, f.filename or "file", data)
    except HTTPException:
        file_storage.delete_job_dir(job.id)
        db.delete(job); db.commit()
        raise

    background_tasks.add_task(cp_jobs.process_tool_job, job.id)
    return JobOut.model_validate(job)


@router.get("/tools/jobs/{job_id}", response_model=JobOut)
def get_client_job_endpoint(
    job_id: int,
    user: User = Depends(require_client_with_device),
    db: Session = Depends(get_db),
):
    try:
        job = cp_service.get_client_job(db, user=user, job_id=job_id)
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))
    return JobOut.model_validate(job)


@router.get("/tools/jobs/{job_id}/download")
def download_client_job_endpoint(
    job_id: int,
    user: User = Depends(require_client_with_device),
    db: Session = Depends(get_db),
):
    try:
        job = cp_service.get_client_job(db, user=user, job_id=job_id)
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))
    if job.status not in ("done", "error_partial"):
        raise HTTPException(409, detail=f"Job status={job.status}, no listo para descarga")
    out_path = file_storage.output_path(file_storage.job_dir(job.id))
    if not out_path.exists():
        raise HTTPException(410, detail="Archivo expirado (>24h). Reprocese.")
    filename = f"{job.tool_code}_{job.id}.bin"  # placeholder; tools reales setean extension
    return StreamingResponse(
        BytesIO(out_path.read_bytes()),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/tools/jobs", response_model=list[JobOut])
def list_client_jobs_endpoint(
    status: str | None = None,
    limit: int = 20,
    user: User = Depends(require_client_with_device),
    db: Session = Depends(get_db),
):
    from sqlalchemy import select
    from backend.app.aud.obligaciones_fiscales.models import ToolJob
    q = select(ToolJob).where(ToolJob.user_id == user.id)
    if status:
        q = q.where(ToolJob.status == status)
    q = q.order_by(ToolJob.created_at.desc()).limit(limit)
    return [JobOut.model_validate(j) for j in db.execute(q).scalars()]
```

- [ ] **Step 5: Run all client portal job tests**

```bash
pytest tests/test_client_portal_jobs.py -v
```
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/client_portal/jobs.py backend/app/client_portal/service.py backend/app/client_portal/router.py
git commit -m "feat(client_portal): job pipeline (create/poll/download/list) reusing OF storage"
```

---

# PHASE 9 — Critical Isolation Tests

## Task 15: Client A cannot access Client B data

**Files:**
- Test: `tests/test_client_isolation.py` (new)

- [ ] **Step 1: Create the test file**

Create `tests/test_client_isolation.py`:

```python
"""CRITICAL: aislamiento entre clientes y entre roles.
Estos tests son no negociables antes de producción.
"""
import io
import pytest
from backend.app.auth.models import Role
from backend.app.auth.service import create_user
from backend.app.auth.jwt_tokens import create_access_token
from backend.app.client_portal.service import create_portal_user
from backend.app.context.models import Organization, Client
from backend.app.db.session import SessionLocal


@pytest.fixture()
def db_session():
    db = SessionLocal()
    yield db
    db.close()


def _make_logged_client(client, db_session, email_prefix):
    org = Organization(name=f"Org-{email_prefix}", slug=f"org-{email_prefix}", is_active=True)
    db_session.add(org); db_session.commit(); db_session.refresh(org)
    cli = Client(organization_id=org.id, name=f"Cli-{email_prefix}", is_active=True)
    db_session.add(cli); db_session.commit(); db_session.refresh(cli)
    email = f"{email_prefix}@iso.com"
    user, pwd = create_portal_user(db_session, client_id=cli.id, email=email)
    # Need fresh TestClient cookies per "device". TestClient shares cookie jar so we'd
    # need a separate TestClient per simulated machine. For this test the second client
    # uses a separate cookie jar via httpx directly.
    from fastapi.testclient import TestClient
    import app as legacy_app
    tc = TestClient(legacy_app.app)
    r = tc.post(
        "/api/v1/client/auth/login",
        data={"username": email, "password": pwd},
    )
    assert r.status_code == 200
    return {
        "user": user, "client_record": cli, "tc": tc,
        "headers": {"Authorization": f"Bearer {r.json()['access_token']}"},
    }


def test_client_a_cannot_get_client_b_job(client, db_session):
    a = _make_logged_client(client, db_session, "alpha")
    b = _make_logged_client(client, db_session, "bravo")

    # A creates a job
    r = a["tc"].post(
        "/api/v1/client/tools/STUB_ECHO/jobs",
        files={"input": ("a.pdf", io.BytesIO(b"%PDF-A"), "application/pdf")},
        headers=a["headers"],
    )
    assert r.status_code == 201
    job_id_a = r.json()["id"]

    # B tries to GET A's job
    r2 = b["tc"].get(
        f"/api/v1/client/tools/jobs/{job_id_a}",
        headers=b["headers"],
    )
    assert r2.status_code == 403

    # B tries to download A's output
    r3 = b["tc"].get(
        f"/api/v1/client/tools/jobs/{job_id_a}/download",
        headers=b["headers"],
    )
    assert r3.status_code == 403


def test_staff_jwt_cannot_access_client_endpoints(client, db_session):
    """Staff con rol admin no debe poder usar rutas /client/*
    (porque le falta cookie device_id Y rol no es client).
    """
    staff = create_user(db_session, email="staff@iso.com", password="x", role=Role.admin)
    token = create_access_token(subject=staff.email, role="admin")
    r = client.get("/api/v1/client/catalog", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


def test_client_jwt_cannot_access_staff_endpoints(client, db_session):
    """Cliente con rol client no debe poder usar /staff/*"""
    org = Organization(name="O-iso", slug="o-iso", is_active=True)
    db_session.add(org); db_session.commit(); db_session.refresh(org)
    cli = Client(organization_id=org.id, name="C-iso", is_active=True)
    db_session.add(cli); db_session.commit(); db_session.refresh(cli)
    user, _ = create_portal_user(db_session, client_id=cli.id, email="cli-iso@x.com")
    token = create_access_token(subject=user.email, role="client")
    r = client.post(
        f"/api/v1/staff/clients/{cli.id}/portal-users",
        json={"email": "wont@happen.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403
```

- [ ] **Step 2: Run + commit**

```bash
pytest tests/test_client_isolation.py -v
git add tests/test_client_isolation.py
git commit -m "test(security): critical isolation tests (client-vs-client + role separation)"
```

---

# PHASE 10 — Email Notifications

## Task 16: Resend email wrapper

**Files:**
- Create: `backend/app/notifications/__init__.py` (empty)
- Create: `backend/app/notifications/email.py`
- Create: `backend/app/notifications/templates/job_ready.html`
- Test: `tests/test_notifications_email.py` (new)

- [ ] **Step 1: Add tests**

Create `tests/test_notifications_email.py`:

```python
"""Tests for notifications.email (Resend wrapper)."""
from unittest.mock import patch, MagicMock
from backend.app.notifications import email as email_mod


def test_render_job_ready_template():
    html = email_mod.render_job_ready(
        client_name="Empresa XYZ",
        tool_label="Anexo ICT 2025",
        download_url="https://example.com/download",
    )
    assert "Empresa XYZ" in html
    assert "Anexo ICT 2025" in html
    assert "https://example.com/download" in html
    assert "24h" in html or "24 horas" in html


@patch("backend.app.notifications.email._post_to_resend")
def test_send_email_retries_on_failure(mock_post):
    # Falla 2 veces, éxito al 3er intento
    mock_post.side_effect = [
        Exception("temporary"),
        Exception("temporary"),
        {"id": "msg_123"},
    ]
    result = email_mod.send_email(
        to="x@example.com", subject="Test", html="<p>x</p>"
    )
    assert result == {"id": "msg_123"}
    assert mock_post.call_count == 3


@patch("backend.app.notifications.email._post_to_resend")
def test_send_email_returns_none_after_max_retries(mock_post):
    mock_post.side_effect = Exception("permanent")
    result = email_mod.send_email(
        to="x@example.com", subject="Test", html="<p>x</p>", max_retries=2
    )
    assert result is None
    assert mock_post.call_count == 2
```

- [ ] **Step 2: Create `backend/app/notifications/__init__.py`** (empty)

- [ ] **Step 3: Create `backend/app/notifications/templates/job_ready.html`**

```html
<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px">
  <div style="border-bottom:3px solid #0a2540;padding-bottom:10px;margin-bottom:20px">
    <h2 style="color:#0a2540;margin:0">Audit Consulting Group</h2>
    <p style="margin:5px 0;color:#666;font-size:13px">Powered by Audit-IA</p>
  </div>

  <p>Hola,</p>
  <p>El procesamiento de tu herramienta <strong>{{tool_label}}</strong> ha finalizado correctamente.</p>

  <p style="text-align:center;margin:30px 0">
    <a href="{{download_url}}"
       style="background:#0a2540;color:#fff;padding:12px 24px;text-decoration:none;border-radius:6px;display:inline-block">
      Descargar entregable
    </a>
  </p>

  <p style="background:#fff3cd;border:1px solid #ffc107;padding:10px;border-radius:4px;font-size:14px">
    <strong>Importante:</strong> Por política de seguridad, este archivo estará disponible solo por <strong>24 horas</strong>.
    Después se eliminará automáticamente del sistema.
  </p>

  <p style="color:#666;font-size:12px;border-top:1px solid #eee;padding-top:15px;margin-top:30px">
    Este es un mensaje automático del Portal Cliente de Audit Consulting Group.
    Si no esperabas este mensaje, contacta a soporte.
  </p>
</body>
</html>
```

- [ ] **Step 4: Create `backend/app/notifications/email.py`**

```python
"""Wrapper de email transaccional con Resend + retry.

Requiere variables de entorno:
- RESEND_API_KEY
- RESEND_FROM_EMAIL (ej. "notificaciones@auditconsulting.com")
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

import requests

log = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_RESEND_URL = "https://api.resend.com/emails"


def render_job_ready(*, client_name: str, tool_label: str, download_url: str) -> str:
    """Renderiza plantilla job_ready.html con sustituciones simples."""
    tpl = (_TEMPLATES_DIR / "job_ready.html").read_text(encoding="utf-8")
    return (
        tpl.replace("{{tool_label}}", tool_label)
        .replace("{{download_url}}", download_url)
        .replace("{{client_name}}", client_name)
    )


def _post_to_resend(*, to: str, subject: str, html: str) -> dict:
    """Hace POST real a Resend. Lanza Exception en cualquier fallo."""
    api_key = os.getenv("RESEND_API_KEY", "").strip()
    from_email = os.getenv("RESEND_FROM_EMAIL", "no-reply@auditconsulting.com").strip()
    if not api_key:
        raise RuntimeError("RESEND_API_KEY no configurado.")
    resp = requests.post(
        _RESEND_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={"from": from_email, "to": [to], "subject": subject, "html": html},
        timeout=15,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Resend {resp.status_code}: {resp.text[:200]}")
    return resp.json()


def send_email(
    *, to: str, subject: str, html: str, max_retries: int = 3
) -> dict | None:
    """Envía email con retry exponencial. Devuelve dict de Resend o None si falló."""
    delay = 1.0
    for attempt in range(1, max_retries + 1):
        try:
            return _post_to_resend(to=to, subject=subject, html=html)
        except Exception as e:  # noqa: BLE001
            log.warning("send_email attempt %d/%d failed: %s", attempt, max_retries, e)
            if attempt < max_retries:
                time.sleep(delay)
                delay *= 2
    log.error("send_email FAILED after %d retries to=%s subject=%r", max_retries, to, subject)
    return None


def send_job_ready_email(*, job_id: int, to: str, tool_label: str) -> dict | None:
    """Helper de alto nivel para notificar job completado."""
    portal_base = os.getenv("CLIENT_PORTAL_URL", "https://auditbrain-clientes.onrender.com")
    download_url = f"{portal_base}/jobs/{job_id}"
    html = render_job_ready(
        client_name="Cliente",
        tool_label=tool_label,
        download_url=download_url,
    )
    return send_email(
        to=to,
        subject=f"Su entregable '{tool_label}' está listo (disponible 24h)",
        html=html,
    )
```

- [ ] **Step 5: Run + commit**

```bash
pytest tests/test_notifications_email.py -v
git add backend/app/notifications/ tests/test_notifications_email.py
git commit -m "feat(notifications): Resend email wrapper with retry + job_ready template"
```

---

## Task 17: Wire email into job completion

**Files:**
- Modify: `backend/app/client_portal/jobs.py`

- [ ] **Step 1: Update `process_tool_job` to send email on success**

In `backend/app/client_portal/jobs.py`, modify the function:

```python
def process_tool_job(job_id: int) -> None:
    """Lee el job, busca su tool_code en el registry, invoca el processor,
    envía email al completar (solo si initiated_from='client' y notify_email seteado).
    """
    from backend.app.aud.obligaciones_fiscales.models import ToolJob
    from backend.app.db.session import SessionLocal
    from backend.app.notifications.email import send_job_ready_email

    db = SessionLocal()
    try:
        job = db.get(ToolJob, job_id)
        if job is None:
            log.error("process_tool_job: job %s not found", job_id)
            return
        tool_code = job.tool_code
        notify_email = job.notify_email
        initiated_from = job.initiated_from
    finally:
        db.close()

    try:
        tool = get_tool(tool_code)
    except KeyError:
        log.error("process_tool_job: tool %s not registered", tool_code)
        _mark_error(job_id, f"Tool {tool_code} no registrada.")
        return

    try:
        tool.processor(job_id)
    except Exception as e:  # noqa: BLE001
        log.exception("process_tool_job %s failed", job_id)
        _mark_error(job_id, str(e))
        return

    # Verificar status final del processor
    db = SessionLocal()
    try:
        job = db.get(ToolJob, job_id)
        final_status = job.status if job else "unknown"
    finally:
        db.close()

    if final_status == "done" and initiated_from == "client" and notify_email:
        try:
            send_job_ready_email(job_id=job_id, to=notify_email, tool_label=tool.label)
        except Exception:
            log.exception("Email notification failed for job %s (non-fatal)", job_id)
```

- [ ] **Step 2: Commit (no new test — email mocked already; manual smoke at end)**

```bash
git add backend/app/client_portal/jobs.py
git commit -m "feat(client_portal): send email notification when client job completes"
```

---

# PHASE 11 — Hardening

## Task 18: Rate limiting on /client/auth/login

**Files:**
- Create: `backend/app/client_portal/rate_limit.py`
- Modify: `backend/app/client_portal/router.py`

- [ ] **Step 1: Create `backend/app/client_portal/rate_limit.py`**

```python
"""Rate limiter en memoria (suficiente para MVP single-instance Render).
Para multi-instance migrar a Redis con sliding window.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

_WINDOWS: dict[str, deque[float]] = defaultdict(deque)
_LOCK = Lock()


def check_and_record(key: str, *, max_hits: int, window_seconds: int) -> bool:
    """Devuelve True si la request está permitida (dentro del límite).
    Devuelve False si excede.
    """
    now = time.monotonic()
    cutoff = now - window_seconds
    with _LOCK:
        bucket = _WINDOWS[key]
        # Drop expired
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= max_hits:
            return False
        bucket.append(now)
        return True


def reset_for_key(key: str) -> None:
    """Utilidad para tests."""
    with _LOCK:
        _WINDOWS.pop(key, None)
```

- [ ] **Step 2: Wire into login endpoint**

In `backend/app/client_portal/router.py`, at top of `client_login` function:

```python
from backend.app.client_portal.rate_limit import check_and_record

@router.post("/auth/login", response_model=ClientLoginResponse)
def client_login(
    request: Request,
    response: Response,
    form: OAuth2PasswordRequestForm = Depends(),
    device_id: str | None = Cookie(default=None, alias="device_id"),
    db: Session = Depends(get_db),
):
    # Rate limit: 5 intentos / 15 min por IP+email
    ip = request.client.host if request.client else "unknown"
    rl_key = f"login:{ip}:{form.username.lower()}"
    if not check_and_record(rl_key, max_hits=5, window_seconds=900):
        raise HTTPException(
            429,
            detail="Demasiados intentos. Espere 15 minutos o contacte a soporte.",
        )
    # ... resto del código existente
```

- [ ] **Step 3: Add test**

Create `tests/test_client_rate_limit.py`:

```python
from backend.app.client_portal.rate_limit import check_and_record, reset_for_key


def test_rate_limit_blocks_after_max_hits():
    reset_for_key("test:abc")
    for _ in range(5):
        assert check_and_record("test:abc", max_hits=5, window_seconds=10) is True
    assert check_and_record("test:abc", max_hits=5, window_seconds=10) is False


def test_rate_limit_separate_keys():
    reset_for_key("test:k1")
    reset_for_key("test:k2")
    for _ in range(5):
        check_and_record("test:k1", max_hits=5, window_seconds=10)
    # k2 should still be allowed
    assert check_and_record("test:k2", max_hits=5, window_seconds=10) is True
```

- [ ] **Step 4: Run + commit**

```bash
pytest tests/test_client_rate_limit.py -v
git add backend/app/client_portal/rate_limit.py backend/app/client_portal/router.py tests/test_client_rate_limit.py
git commit -m "feat(client_portal): in-memory rate limiter on login (5/15min/IP+email)"
```

---

## Task 19: Zombie job detector in cleanup

**Files:**
- Modify: `backend/app/aud/obligaciones_fiscales/cleanup.py`
- Test: `tests/test_zombie_cleanup.py` (new)

- [ ] **Step 1: Add test**

Create `tests/test_zombie_cleanup.py`:

```python
"""Test: jobs en 'processing' por más de 30 min → marcados 'error' automáticamente."""
import datetime
import pytest
from backend.app.aud.obligaciones_fiscales.cleanup import cleanup_once
from backend.app.aud.obligaciones_fiscales.models import ToolJob
from backend.app.auth.service import create_user
from backend.app.auth.models import Role
from backend.app.context.models import Organization, Client, Project
from backend.app.db.session import SessionLocal


def test_zombie_processing_job_marked_error():
    db = SessionLocal()
    try:
        org = Organization(name="ZO", slug="z-o", is_active=True)
        db.add(org); db.commit(); db.refresh(org)
        cli = Client(organization_id=org.id, name="ZC", is_active=True)
        db.add(cli); db.commit(); db.refresh(cli)
        proj = Project(organization_id=org.id, client_id=cli.id, name="ZP")
        db.add(proj); db.commit(); db.refresh(proj)
        u = create_user(db, "zombie@x.com", "x", Role.client)

        now = datetime.datetime.utcnow()
        job = ToolJob(
            user_id=u.id, project_id=proj.id, tool_code="STUB_ECHO",
            status="processing", cliente_name="x", period_label="x",
            created_at=now - datetime.timedelta(hours=2),
            expires_at=now + datetime.timedelta(hours=22),  # not expired yet
            initiated_from="client",
        )
        db.add(job); db.commit(); db.refresh(job)

        summary = cleanup_once()
        db.refresh(job)
        assert job.status == "error"
        assert "zombie" in (job.error_message or "").lower() or "tiempo" in (job.error_message or "").lower()
        assert summary.get("zombie_jobs", 0) >= 1
    finally:
        db.close()
```

- [ ] **Step 2: Modify `backend/app/aud/obligaciones_fiscales/cleanup.py`**

Add a new block inside `cleanup_once()` before the `db.commit()`:

```python
        # 4. Zombie jobs: status 'processing' por > 30 min → error
        summary["zombie_jobs"] = 0
        zombie_threshold = now - datetime.timedelta(minutes=30)
        zombies = db.execute(
            select(ToolJob).where(
                ToolJob.status == "processing",
                ToolJob.created_at < zombie_threshold,
            )
        ).scalars().all()
        for j in zombies:
            j.status = "error"
            j.error_message = (
                "Tiempo de procesamiento excedido (zombie detectado por cleanup). "
                "Reintenta el trabajo."
            )
            db.add(j)
            summary["zombie_jobs"] += 1
```

Add `summary["zombie_jobs"] = 0` to the initial summary dict:

```python
    summary = {"expired_jobs": 0, "post_download_cleanups": 0, "orphan_dirs": 0, "zombie_jobs": 0}
```

- [ ] **Step 3: Run + commit**

```bash
pytest tests/test_zombie_cleanup.py -v
git add backend/app/aud/obligaciones_fiscales/cleanup.py tests/test_zombie_cleanup.py
git commit -m "feat(cleanup): zombie job detector (processing > 30min → error)"
```

---

## Task 20: CORS for new origins

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Update CORS origins**

In `app.py`, find the CORS block and update the env hint comment:

```python
# Ejemplo: CORS_ALLOW_ORIGINS="https://auditbrain-app.onrender.com,https://auditbrain-clientes.onrender.com"
```

Also: in Render dashboard, set `CORS_ALLOW_ORIGINS` env var to include both:
- `https://auditbrain-app.onrender.com`
- `https://auditbrain-clientes.onrender.com`

- [ ] **Step 2: Commit doc change**

```bash
git add app.py
git commit -m "docs(cors): document client portal origin for CORS_ALLOW_ORIGINS env"
```

---

# PHASE 12 — Frontend Shared Workspace

## Task 21: Setup `frontend-shared/` workspace

**Files:**
- Create: `frontend-shared/package.json`
- Create: `frontend-shared/src/Button.jsx`
- Create: `frontend-shared/src/Input.jsx`
- Create: `frontend-shared/src/Modal.jsx`
- Create: `frontend-shared/src/ProgressBar.jsx`
- Create: `frontend-shared/src/index.js`

- [ ] **Step 1: Create `frontend-shared/package.json`**

```json
{
  "name": "@auditbrain/shared",
  "version": "0.1.0",
  "private": true,
  "main": "src/index.js",
  "type": "module",
  "peerDependencies": {
    "react": "^18.3.1"
  }
}
```

- [ ] **Step 2: Create `frontend-shared/src/Button.jsx`**

```jsx
export function Button({ children, variant = "primary", ...rest }) {
  const styles = {
    primary: { background: "#0a2540", color: "#fff" },
    secondary: { background: "#fff", color: "#0a2540", border: "1px solid #0a2540" },
    danger: { background: "#c0392b", color: "#fff" },
  };
  return (
    <button
      style={{
        padding: "10px 18px",
        borderRadius: 6,
        border: "none",
        fontWeight: 600,
        cursor: "pointer",
        ...styles[variant],
      }}
      {...rest}
    >
      {children}
    </button>
  );
}
```

- [ ] **Step 3: Create `frontend-shared/src/Input.jsx`**

```jsx
export function Input({ label, error, ...rest }) {
  return (
    <div style={{ marginBottom: 12 }}>
      {label && (
        <label style={{ display: "block", marginBottom: 4, fontSize: 13, color: "#555" }}>
          {label}
        </label>
      )}
      <input
        style={{
          width: "100%",
          padding: "10px 12px",
          borderRadius: 6,
          border: error ? "1px solid #c0392b" : "1px solid #ccc",
          fontSize: 14,
          boxSizing: "border-box",
        }}
        {...rest}
      />
      {error && (
        <div style={{ color: "#c0392b", fontSize: 12, marginTop: 4 }}>{error}</div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Create `frontend-shared/src/Modal.jsx`**

```jsx
export function Modal({ open, onClose, title, children }) {
  if (!open) return null;
  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)",
        display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: "#fff", borderRadius: 8, padding: 24,
          maxWidth: 480, width: "90%", boxShadow: "0 10px 30px rgba(0,0,0,0.3)",
        }}
      >
        {title && <h3 style={{ marginTop: 0 }}>{title}</h3>}
        {children}
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Create `frontend-shared/src/ProgressBar.jsx`**

```jsx
export function ProgressBar({ value = 0, label }) {
  const pct = Math.min(100, Math.max(0, value));
  return (
    <div style={{ marginBottom: 12 }}>
      {label && (
        <div style={{ fontSize: 13, marginBottom: 4, color: "#555" }}>{label}</div>
      )}
      <div style={{ background: "#eee", borderRadius: 4, overflow: "hidden", height: 10 }}>
        <div
          style={{
            background: "#0a2540", height: "100%", width: `${pct}%`,
            transition: "width 0.3s ease",
          }}
        />
      </div>
    </div>
  );
}
```

- [ ] **Step 6: Create `frontend-shared/src/index.js`**

```js
export { Button } from "./Button.jsx";
export { Input } from "./Input.jsx";
export { Modal } from "./Modal.jsx";
export { ProgressBar } from "./ProgressBar.jsx";
```

- [ ] **Step 7: Commit**

```bash
git add frontend-shared/
git commit -m "feat(frontend-shared): UI components workspace (Button/Input/Modal/ProgressBar)"
```

---

# PHASE 13 — Frontend Client Scaffold

## Task 22: Vite scaffold + API client + Router

**Files:**
- Create: `frontend-client/package.json`
- Create: `frontend-client/vite.config.js`
- Create: `frontend-client/index.html`
- Create: `frontend-client/src/main.jsx`
- Create: `frontend-client/src/api.js`
- Create: `frontend-client/src/auth/AuthProvider.jsx`
- Create: `frontend-client/src/App.jsx`

- [ ] **Step 1: Create `frontend-client/package.json`**

```json
{
  "name": "auditbrain-frontend-client",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.26.0",
    "@auditbrain/shared": "file:../frontend-shared"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.1",
    "vite": "^5.4.2"
  }
}
```

- [ ] **Step 2: Create `frontend-client/vite.config.js`**

```js
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: { port: 5174 },
  build: { outDir: "dist" },
});
```

- [ ] **Step 3: Create `frontend-client/index.html`**

```html
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Audit Consulting Group · Portal Cliente</title>
  <link rel="icon" type="image/png" href="/assets/logo-auditconsulting-group.png" />
  <style>
    body { margin: 0; font-family: Arial, sans-serif; background: #f7f9fc; color: #0a2540; }
    * { box-sizing: border-box; }
    a { color: #0a2540; }
  </style>
</head>
<body>
  <div id="root"></div>
  <script type="module" src="/src/main.jsx"></script>
</body>
</html>
```

- [ ] **Step 4: Create `frontend-client/src/main.jsx`**

```jsx
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App.jsx";
import { AuthProvider } from "./auth/AuthProvider.jsx";

ReactDOM.createRoot(document.getElementById("root")).render(
  <BrowserRouter>
    <AuthProvider>
      <App />
    </AuthProvider>
  </BrowserRouter>
);
```

- [ ] **Step 5: Create `frontend-client/src/api.js`**

```js
const BASE = import.meta.env.VITE_API_BASE || "https://auditbrain-api.onrender.com";

let _token = localStorage.getItem("ab_client_token") || null;

export function setToken(t) {
  _token = t;
  if (t) localStorage.setItem("ab_client_token", t);
  else localStorage.removeItem("ab_client_token");
}

export function getToken() {
  return _token;
}

async function request(path, opts = {}) {
  const headers = { ...(opts.headers || {}) };
  if (_token) headers["Authorization"] = `Bearer ${_token}`;
  const resp = await fetch(`${BASE}/api/v1${path}`, {
    ...opts,
    headers,
    credentials: "include", // crítico para cookie device_id
  });
  let body = null;
  try { body = await resp.json(); } catch { /* ignore */ }
  if (!resp.ok) {
    const err = new Error(body?.detail?.message || body?.detail || `HTTP ${resp.status}`);
    err.status = resp.status;
    err.code = body?.detail?.code;
    err.body = body;
    throw err;
  }
  return body;
}

export async function login(email, password) {
  const fd = new FormData();
  fd.append("username", email);
  fd.append("password", password);
  const r = await fetch(`${BASE}/api/v1/client/auth/login`, {
    method: "POST",
    body: fd,
    credentials: "include",
  });
  const body = await r.json();
  if (!r.ok) {
    const err = new Error(body?.detail?.message || body?.detail || `HTTP ${r.status}`);
    err.status = r.status; err.code = body?.detail?.code; throw err;
  }
  setToken(body.access_token);
  return body;
}

export async function logout() {
  try { await request("/client/auth/logout", { method: "POST" }); }
  finally { setToken(null); }
}

export const me = () => request("/client/auth/me");
export const changePassword = (old_password, new_password) =>
  request("/client/auth/change-password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ old_password, new_password }),
  });
export const getCatalog = () => request("/client/catalog");
export const listJobs = (status = null, limit = 20) => {
  const qs = new URLSearchParams();
  if (status) qs.set("status", status);
  qs.set("limit", limit);
  return request(`/client/tools/jobs?${qs}`);
};
export const getJob = (jobId) => request(`/client/tools/jobs/${jobId}`);
export const createJob = async (toolCode, fileMap) => {
  // fileMap: { slotName: File or [File, ...] }
  const fd = new FormData();
  for (const [slot, val] of Object.entries(fileMap)) {
    const arr = Array.isArray(val) ? val : [val];
    for (const f of arr) fd.append(slot, f);
  }
  return request(`/client/tools/${toolCode}/jobs`, { method: "POST", body: fd });
};
export const downloadJobUrl = (jobId) =>
  `${BASE}/api/v1/client/tools/jobs/${jobId}/download`;
```

- [ ] **Step 6: Create `frontend-client/src/auth/AuthProvider.jsx`**

```jsx
import { createContext, useContext, useState, useEffect, useCallback } from "react";
import * as api from "../api.js";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [sessionInvalidated, setSessionInvalidated] = useState(false);

  const refresh = useCallback(async () => {
    if (!api.getToken()) {
      setUser(null); setLoading(false); return;
    }
    try {
      const me = await api.me();
      setUser(me);
    } catch (e) {
      if (e.code === "session_invalidated") setSessionInvalidated(true);
      setUser(null);
      api.setToken(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const login = async (email, password) => {
    const r = await api.login(email, password);
    await refresh();
    return r;
  };

  const logout = async () => {
    await api.logout();
    setUser(null);
  };

  return (
    <AuthCtx.Provider value={{
      user, loading, login, logout, refresh,
      sessionInvalidated, clearSessionFlag: () => setSessionInvalidated(false),
    }}>
      {children}
    </AuthCtx.Provider>
  );
}

export const useAuth = () => useContext(AuthCtx);
```

- [ ] **Step 7: Create `frontend-client/src/App.jsx`** (minimal skeleton; pages added in later tasks)

```jsx
import { Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "./auth/AuthProvider.jsx";

// Placeholders — implementadas en tareas posteriores
function Landing() { return <div style={{padding:40}}>Landing (pendiente)</div>; }
function Login() { return <div style={{padding:40}}>Login (pendiente)</div>; }
function Catalog() { return <div style={{padding:40}}>Catálogo (pendiente)</div>; }

function Protected({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div style={{padding:40}}>Cargando...</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (user.password_reset_required) return <Navigate to="/change-password" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/catalog" element={<Protected><Catalog /></Protected>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
```

- [ ] **Step 8: Install + smoke build**

```bash
cd frontend-client && npm install && npm run build && cd ..
```

Expected: build succeeds, `dist/` created.

- [ ] **Step 9: Commit**

```bash
git add frontend-client/
git commit -m "feat(frontend-client): scaffold Vite + AuthProvider + API client + router skeleton"
```

---

## Task 23: Landing page

**Files:**
- Create: `frontend-client/src/landing/Landing.jsx`
- Create: `frontend-client/src/landing/Hero.jsx`
- Create: `frontend-client/src/landing/Features.jsx`
- Create: `frontend-client/src/landing/CTAs.jsx`
- Modify: `frontend-client/src/App.jsx`

- [ ] **Step 1: Create `Hero.jsx`**

```jsx
import { Button } from "@auditbrain/shared";
import { useNavigate } from "react-router-dom";

export function Hero() {
  const nav = useNavigate();
  return (
    <section style={{ background: "#0a2540", color: "#fff", padding: "80px 20px", textAlign: "center" }}>
      <h1 style={{ fontSize: 42, margin: 0 }}>
        Automatiza tu cumplimiento tributario y NIIF
      </h1>
      <p style={{ fontSize: 18, maxWidth: 700, margin: "16px auto", opacity: 0.9 }}>
        Sube tus documentos contables y descarga entregables ya llenados en minutos.
        Procesos auditados, seguros y disponibles por solo 24h por tu privacidad.
      </p>
      <div style={{ marginTop: 30 }}>
        <Button onClick={() => nav("/login")}>Ingresar al portal</Button>
      </div>
      <p style={{ fontSize: 13, marginTop: 24, opacity: 0.7 }}>
        Audit Consulting Group · Powered by <strong>Audit-IA</strong>
      </p>
    </section>
  );
}
```

- [ ] **Step 2: Create `Features.jsx`**

```jsx
const FEATURES = [
  { icon: "📄", title: "Anexo ICT 2025", desc: "Cumplimiento tributario SRI automatizado." },
  { icon: "💰", title: "NIIF 9 — ECL", desc: "Matriz de pérdidas esperadas en cartera." },
  { icon: "📦", title: "Inventarios NIC 2", desc: "Valor Neto Realización y obsolescencia." },
  { icon: "🏢", title: "Activos Fijos", desc: "Depreciación, deterioro y arrendamientos." },
  { icon: "🧾", title: "NIIF 15 Ingresos", desc: "Reconocimiento por obligaciones." },
  { icon: "🛡️", title: "Seguridad estricta", desc: "Datos eliminados a las 24h. Dispositivo vinculado." },
];

export function Features() {
  return (
    <section style={{ padding: "60px 20px", maxWidth: 1100, margin: "0 auto" }}>
      <h2 style={{ textAlign: "center", marginBottom: 40 }}>Herramientas disponibles</h2>
      <div style={{
        display: "grid", gap: 20,
        gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
      }}>
        {FEATURES.map((f) => (
          <div key={f.title} style={{
            background: "#fff", padding: 24, borderRadius: 8,
            boxShadow: "0 2px 8px rgba(0,0,0,0.05)",
          }}>
            <div style={{ fontSize: 32, marginBottom: 12 }}>{f.icon}</div>
            <h3 style={{ margin: "0 0 8px", fontSize: 18 }}>{f.title}</h3>
            <p style={{ color: "#555", fontSize: 14, margin: 0 }}>{f.desc}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
```

- [ ] **Step 3: Create `CTAs.jsx`**

```jsx
import { Button } from "@auditbrain/shared";
import { useNavigate } from "react-router-dom";

export function CTAs() {
  const nav = useNavigate();
  return (
    <section style={{ background: "#fff", padding: "60px 20px", textAlign: "center", borderTop: "1px solid #e0e6ed" }}>
      <h2 style={{ marginTop: 0 }}>¿Ya tienes cuenta?</h2>
      <p style={{ color: "#555", marginBottom: 24 }}>
        Tu cuenta fue creada por el equipo de Audit Consulting Group.
        Solicita tus credenciales si aún no las has recibido.
      </p>
      <Button onClick={() => nav("/login")}>Ingresar</Button>
      <p style={{ marginTop: 30, fontSize: 13, color: "#888" }}>
        ¿Aún no eres cliente? Escríbenos: <a href="mailto:contacto@auditconsulting.com">contacto@auditconsulting.com</a>
      </p>
    </section>
  );
}
```

- [ ] **Step 4: Create `Landing.jsx`**

```jsx
import { Hero } from "./Hero.jsx";
import { Features } from "./Features.jsx";
import { CTAs } from "./CTAs.jsx";

export default function Landing() {
  return (
    <>
      <Hero />
      <Features />
      <CTAs />
      <footer style={{ background: "#0a2540", color: "#fff", textAlign: "center", padding: 20, fontSize: 12 }}>
        © {new Date().getFullYear()} Audit Consulting Group · Powered by Audit-IA
      </footer>
    </>
  );
}
```

- [ ] **Step 5: Wire in `App.jsx`**

Replace the placeholder Landing import:

```jsx
import Landing from "./landing/Landing.jsx";
// remove the local function Landing
```

- [ ] **Step 6: Build + commit**

```bash
cd frontend-client && npm run build && cd ..
git add frontend-client/
git commit -m "feat(frontend-client): public landing page (Hero + Features + CTAs)"
```

---

## Task 24: Login + Change Password + Device Blocked pages

**Files:**
- Create: `frontend-client/src/auth/Login.jsx`
- Create: `frontend-client/src/auth/ChangePassword.jsx`
- Create: `frontend-client/src/auth/DeviceBlocked.jsx`
- Modify: `frontend-client/src/App.jsx`

- [ ] **Step 1: Create `Login.jsx`**

```jsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button, Input } from "@auditbrain/shared";
import { useAuth } from "./AuthProvider.jsx";

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [pwd, setPwd] = useState("");
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setErr(null); setBusy(true);
    try {
      const r = await login(email, pwd);
      if (r.password_reset_required) nav("/change-password");
      else nav("/catalog");
    } catch (e2) {
      if (e2.code === "device_unauthorized") nav("/device-blocked");
      else setErr(e2.message || "Error al iniciar sesión.");
    } finally { setBusy(false); }
  }

  return (
    <div style={{ maxWidth: 380, margin: "60px auto", padding: 30, background: "#fff", borderRadius: 8, boxShadow: "0 2px 10px rgba(0,0,0,0.08)" }}>
      <h2 style={{ marginTop: 0, textAlign: "center" }}>Portal Cliente</h2>
      <p style={{ textAlign: "center", color: "#666", fontSize: 13, marginBottom: 24 }}>
        Audit Consulting Group · Powered by Audit-IA
      </p>
      <form onSubmit={submit}>
        <Input label="Correo electrónico" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        <Input label="Contraseña" type="password" required value={pwd} onChange={(e) => setPwd(e.target.value)} />
        {err && <div style={{ color: "#c0392b", fontSize: 13, marginBottom: 12 }}>{err}</div>}
        <Button type="submit" disabled={busy} style={{ width: "100%" }}>
          {busy ? "Ingresando..." : "Ingresar"}
        </Button>
      </form>
    </div>
  );
}
```

- [ ] **Step 2: Create `ChangePassword.jsx`**

```jsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button, Input } from "@auditbrain/shared";
import { useAuth } from "./AuthProvider.jsx";
import { changePassword } from "../api.js";

export default function ChangePassword() {
  const { refresh, user } = useAuth();
  const nav = useNavigate();
  const [oldP, setOldP] = useState("");
  const [newP, setNewP] = useState("");
  const [newP2, setNewP2] = useState("");
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setErr(null);
    if (newP !== newP2) { setErr("Las contraseñas nuevas no coinciden."); return; }
    if (newP.length < 8) { setErr("Mínimo 8 caracteres."); return; }
    setBusy(true);
    try {
      await changePassword(oldP, newP);
      await refresh();
      nav("/catalog");
    } catch (e2) {
      setErr(e2.message);
    } finally { setBusy(false); }
  }

  return (
    <div style={{ maxWidth: 420, margin: "60px auto", padding: 30, background: "#fff", borderRadius: 8, boxShadow: "0 2px 10px rgba(0,0,0,0.08)" }}>
      <h2 style={{ marginTop: 0 }}>Cambia tu contraseña</h2>
      <p style={{ color: "#666", fontSize: 13 }}>
        Por seguridad, debes establecer una nueva contraseña antes de continuar.
      </p>
      <form onSubmit={submit}>
        <Input label="Contraseña actual (temporal)" type="password" required value={oldP} onChange={(e) => setOldP(e.target.value)} />
        <Input label="Nueva contraseña (mín. 8 caracteres)" type="password" required value={newP} onChange={(e) => setNewP(e.target.value)} />
        <Input label="Repite la nueva contraseña" type="password" required value={newP2} onChange={(e) => setNewP2(e.target.value)} />
        {err && <div style={{ color: "#c0392b", fontSize: 13, marginBottom: 12 }}>{err}</div>}
        <Button type="submit" disabled={busy} style={{ width: "100%" }}>
          {busy ? "Cambiando..." : "Cambiar contraseña"}
        </Button>
      </form>
    </div>
  );
}
```

- [ ] **Step 3: Create `DeviceBlocked.jsx`**

```jsx
export default function DeviceBlocked() {
  return (
    <div style={{ maxWidth: 480, margin: "80px auto", padding: 30, background: "#fff", borderRadius: 8, textAlign: "center", boxShadow: "0 2px 10px rgba(0,0,0,0.08)" }}>
      <div style={{ fontSize: 48, marginBottom: 16 }}>🛡️</div>
      <h2>Dispositivo no autorizado</h2>
      <p style={{ color: "#555" }}>
        Por política de seguridad, tu cuenta solo permite acceso desde un único computador.
        Este equipo no está registrado o tu dispositivo previo fue revocado.
      </p>
      <p style={{ color: "#555" }}>
        Solicita al equipo de Audit Consulting Group que autorice este nuevo equipo:
      </p>
      <p style={{ background: "#f4f7fb", padding: 12, borderRadius: 6, fontWeight: 600 }}>
        soporte@auditconsulting.com
      </p>
    </div>
  );
}
```

- [ ] **Step 4: Wire in `App.jsx`**

```jsx
import Landing from "./landing/Landing.jsx";
import Login from "./auth/Login.jsx";
import ChangePassword from "./auth/ChangePassword.jsx";
import DeviceBlocked from "./auth/DeviceBlocked.jsx";
import { useAuth } from "./auth/AuthProvider.jsx";
import { Routes, Route, Navigate } from "react-router-dom";

// Catalog placeholder for now (Task 25 builds it)
function Catalog() { return <div style={{padding:40}}>Catálogo (Task 25)</div>; }

function Protected({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div style={{padding:40}}>Cargando...</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (user.password_reset_required) return <Navigate to="/change-password" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/change-password" element={<ChangePassword />} />
      <Route path="/device-blocked" element={<DeviceBlocked />} />
      <Route path="/catalog" element={<Protected><Catalog /></Protected>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
```

- [ ] **Step 5: Build + commit**

```bash
cd frontend-client && npm run build && cd ..
git add frontend-client/
git commit -m "feat(frontend-client): Login + ChangePassword + DeviceBlocked pages"
```

---

## Task 25: Catalog + Tool Shell + Job Progress

**Files:**
- Create: `frontend-client/src/catalog/ClientCatalog.jsx`
- Create: `frontend-client/src/tools/ToolShell.jsx`
- Create: `frontend-client/src/tools/JobProgress.jsx`
- Create: `frontend-client/src/shared/usePolling.js`
- Modify: `frontend-client/src/App.jsx`

- [ ] **Step 1: Create `usePolling.js`**

```js
import { useEffect, useRef } from "react";

export function usePolling(fn, intervalMs = 2000, enabled = true) {
  const fnRef = useRef(fn);
  useEffect(() => { fnRef.current = fn; }, [fn]);
  useEffect(() => {
    if (!enabled) return;
    let stopped = false;
    const tick = async () => {
      if (stopped) return;
      try { await fnRef.current(); } catch (_) { /* ignore */ }
      if (!stopped) setTimeout(tick, intervalMs);
    };
    tick();
    return () => { stopped = true; };
  }, [intervalMs, enabled]);
}
```

- [ ] **Step 2: Create `ClientCatalog.jsx`**

```jsx
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getCatalog } from "../api.js";
import { useAuth } from "../auth/AuthProvider.jsx";

export default function ClientCatalog() {
  const { logout } = useAuth();
  const nav = useNavigate();
  const [cats, setCats] = useState([]);
  const [err, setErr] = useState(null);

  useEffect(() => {
    getCatalog().then((r) => setCats(r.categories)).catch((e) => setErr(e.message));
  }, []);

  return (
    <div>
      <header style={{ background: "#0a2540", color: "#fff", padding: "16px 24px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <strong>Audit Consulting Group</strong>
          <span style={{ marginLeft: 8, opacity: 0.7, fontSize: 13 }}>· Powered by Audit-IA</span>
        </div>
        <button onClick={() => logout().then(() => nav("/login"))}
          style={{ background: "transparent", color: "#fff", border: "1px solid #fff", padding: "6px 14px", borderRadius: 6, cursor: "pointer" }}>
          Cerrar sesión
        </button>
      </header>

      <main style={{ maxWidth: 1100, margin: "30px auto", padding: 20 }}>
        <h1>Tus herramientas</h1>
        {err && <div style={{ color: "#c0392b" }}>{err}</div>}
        {cats.map((cat) => (
          <section key={cat.id} style={{ marginBottom: 32 }}>
            <h3 style={{ borderBottom: "2px solid #0a2540", paddingBottom: 6 }}>{cat.label}</h3>
            {cat.tools.length === 0 ? (
              <p style={{ color: "#888", fontStyle: "italic" }}>Próximamente</p>
            ) : (
              <div style={{ display: "grid", gap: 16, gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))" }}>
                {cat.tools.map((t) => (
                  <button key={t.code}
                    onClick={() => nav(`/tools/${t.code}`)}
                    style={{ textAlign: "left", background: "#fff", padding: 20, borderRadius: 8, border: "1px solid #e0e6ed", cursor: "pointer" }}>
                    <strong>{t.label}</strong>
                    <p style={{ color: "#555", fontSize: 14 }}>{t.description}</p>
                  </button>
                ))}
              </div>
            )}
          </section>
        ))}
      </main>
    </div>
  );
}
```

- [ ] **Step 3: Create `ToolShell.jsx`**

```jsx
import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Button } from "@auditbrain/shared";
import { getCatalog, createJob } from "../api.js";
import JobProgress from "./JobProgress.jsx";

export default function ToolShell() {
  const { toolCode } = useParams();
  const nav = useNavigate();
  const [tool, setTool] = useState(null);
  const [files, setFiles] = useState({}); // {slot: File or [File,...]}
  const [jobId, setJobId] = useState(null);
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getCatalog().then((r) => {
      for (const c of r.categories) {
        const t = c.tools.find((x) => x.code === toolCode);
        if (t) { setTool(t); return; }
      }
      setErr("Herramienta no encontrada.");
    }).catch((e) => setErr(e.message));
  }, [toolCode]);

  function onFileChange(slotName, fileList, multi) {
    setFiles((prev) => ({
      ...prev,
      [slotName]: multi ? Array.from(fileList) : fileList[0] || null,
    }));
  }

  async function submit() {
    setErr(null); setBusy(true);
    try {
      const r = await createJob(toolCode, files);
      setJobId(r.id);
    } catch (e) {
      setErr(e.message);
    } finally { setBusy(false); }
  }

  if (!tool) return <div style={{padding:30}}>{err || "Cargando..."}</div>;
  if (jobId) return <JobProgress jobId={jobId} onClose={() => nav("/catalog")} />;

  return (
    <div style={{ maxWidth: 720, margin: "30px auto", padding: 20 }}>
      <button onClick={() => nav("/catalog")} style={{ background: "none", border: "none", color: "#0a2540", cursor: "pointer", marginBottom: 16 }}>
        ← Volver al catálogo
      </button>
      <h2>{tool.label}</h2>
      <p style={{ color: "#555" }}>{tool.description}</p>

      <div style={{ background: "#fff", padding: 24, borderRadius: 8, marginTop: 20 }}>
        {tool.slots.map((s) => (
          <div key={s.name} style={{ marginBottom: 16 }}>
            <label style={{ display: "block", fontWeight: 600, marginBottom: 6 }}>
              {s.name} {s.required && <span style={{ color: "#c0392b" }}>*</span>}
            </label>
            <input
              type="file"
              accept={s.mimes_allowed.join(",")}
              multiple={s.multi}
              onChange={(e) => onFileChange(s.name, e.target.files, s.multi)}
            />
            <div style={{ fontSize: 12, color: "#888", marginTop: 4 }}>
              Tipos permitidos: {s.mimes_allowed.join(", ")} {s.multi && "(múltiples)"}
            </div>
          </div>
        ))}
        {err && <div style={{ color: "#c0392b", marginBottom: 12 }}>{err}</div>}
        <Button onClick={submit} disabled={busy}>
          {busy ? "Enviando..." : "Procesar"}
        </Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create `JobProgress.jsx`**

```jsx
import { useEffect, useState } from "react";
import { Button, ProgressBar } from "@auditbrain/shared";
import { getJob, downloadJobUrl } from "../api.js";
import { usePolling } from "../shared/usePolling.js";

export default function JobProgress({ jobId, onClose }) {
  const [job, setJob] = useState(null);
  const [err, setErr] = useState(null);

  const isTerminal = job && ["done", "error", "error_partial", "expired"].includes(job.status);

  usePolling(async () => {
    try {
      const j = await getJob(jobId);
      setJob(j);
    } catch (e) { setErr(e.message); }
  }, 2000, !isTerminal);

  if (err) return <div style={{padding:30, color:"#c0392b"}}>Error: {err}</div>;
  if (!job) return <div style={{padding:30}}>Cargando estado...</div>;

  const statusMap = {
    pending: { pct: 10, label: "En cola..." },
    processing: { pct: 60, label: "Procesando..." },
    done: { pct: 100, label: "¡Listo!" },
    error: { pct: 100, label: "Falló" },
    error_partial: { pct: 100, label: "Completado con advertencias" },
    expired: { pct: 100, label: "Expirado" },
  };
  const s = statusMap[job.status] || { pct: 0, label: job.status };

  return (
    <div style={{ maxWidth: 600, margin: "60px auto", padding: 30, background: "#fff", borderRadius: 8 }}>
      <h2>Trabajo #{job.id}</h2>
      <ProgressBar value={s.pct} label={s.label} />
      {job.status === "done" && (
        <a href={downloadJobUrl(job.id)} target="_blank" rel="noreferrer">
          <Button style={{ marginTop: 16 }}>Descargar entregable</Button>
        </a>
      )}
      {job.status === "error" && (
        <div style={{ color: "#c0392b", marginTop: 12, background: "#fdecea", padding: 12, borderRadius: 6 }}>
          {job.error_message || "Error desconocido."}
        </div>
      )}
      <div style={{ marginTop: 24 }}>
        <Button variant="secondary" onClick={onClose}>Volver al catálogo</Button>
      </div>
      <p style={{ fontSize: 12, color: "#888", marginTop: 20 }}>
        Por política de seguridad, este archivo estará disponible solo 24 horas.
      </p>
    </div>
  );
}
```

- [ ] **Step 5: Wire in `App.jsx`**

```jsx
import ClientCatalog from "./catalog/ClientCatalog.jsx";
import ToolShell from "./tools/ToolShell.jsx";

// Replace Catalog placeholder with real ClientCatalog
// Add new route:
<Route path="/tools/:toolCode" element={<Protected><ToolShell /></Protected>} />
<Route path="/catalog" element={<Protected><ClientCatalog /></Protected>} />
```

- [ ] **Step 6: Build + commit**

```bash
cd frontend-client && npm run build && cd ..
git add frontend-client/
git commit -m "feat(frontend-client): catalog + tool shell + job progress with polling"
```

---

# PHASE 14 — Render Deploy + Smoke

## Task 26: Update `render.yaml` for client portal static site

**Files:**
- Modify: `render.yaml`

- [ ] **Step 1: Inspect current render.yaml**

```bash
cat render.yaml
```

- [ ] **Step 2: Add a new `staticSite` block for `frontend-client`**

Append to `render.yaml` (adapt names to current convention):

```yaml
  - type: web
    name: auditbrain-clientes
    runtime: static
    buildCommand: cd frontend-shared && npm install && cd ../frontend-client && npm install && npm run build
    staticPublishPath: ./frontend-client/dist
    envVars:
      - key: VITE_API_BASE
        value: https://auditbrain-api.onrender.com
    routes:
      - type: rewrite
        source: /*
        destination: /index.html
```

(Exact Render schema may differ — verify against existing entries; the key idea is: static site, build command spans both shared + client, publish dist.)

- [ ] **Step 3: Commit**

```bash
git add render.yaml
git commit -m "deploy(render): add auditbrain-clientes static site for portal cliente"
```

- [ ] **Step 4: Deploy via Render dashboard**

Manual steps (not in plan but checklist):
1. Push branch + open PR
2. Merge to main
3. In Render dashboard: confirm new service `auditbrain-clientes` provisions
4. In existing backend service: set env `CORS_ALLOW_ORIGINS=https://auditbrain-app.onrender.com,https://auditbrain-clientes.onrender.com`
5. In existing backend service: set env `RESEND_API_KEY=<from Resend dashboard>` and `RESEND_FROM_EMAIL=no-reply@<your verified domain>`
6. Smoke test: visit `https://auditbrain-clientes.onrender.com`, create test client via staff portal, login, run STUB_ECHO job

---

# PHASE 15 — E2E (Playwright) — Critical Smokes Only

## Task 27: Playwright setup + happy path

**Files:**
- Create: `e2e/package.json`
- Create: `e2e/playwright.config.js`
- Create: `e2e/tests/happy-path.spec.js`

- [ ] **Step 1: Create `e2e/package.json`**

```json
{
  "name": "auditbrain-e2e",
  "private": true,
  "version": "0.1.0",
  "scripts": {
    "test": "playwright test"
  },
  "devDependencies": {
    "@playwright/test": "^1.47.0"
  }
}
```

- [ ] **Step 2: Create `e2e/playwright.config.js`**

```js
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  use: {
    baseURL: process.env.E2E_BASE_URL || "https://auditbrain-clientes.onrender.com",
    headless: true,
    screenshot: "only-on-failure",
  },
  reporter: "list",
});
```

- [ ] **Step 3: Create `e2e/tests/happy-path.spec.js`**

```js
import { test, expect } from "@playwright/test";

test("landing → login redirect", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText(/Audit Consulting Group/i)).toBeVisible();
  await page.getByRole("button", { name: /Ingresar/i }).first().click();
  await expect(page).toHaveURL(/\/login/);
});

test("login with invalid credentials shows error", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel(/Correo/i).fill("noexiste@example.com");
  await page.getByLabel(/Contraseña/i).fill("wrong");
  await page.getByRole("button", { name: /Ingresar/i }).click();
  await expect(page.getByText(/Credenciales/i)).toBeVisible({ timeout: 5000 });
});
```

- [ ] **Step 4: Install + smoke run (against local dev or deployed)**

```bash
cd e2e && npm install && npx playwright install chromium && cd ..
# Local: E2E_BASE_URL=http://localhost:5174 npx playwright test --config=e2e/playwright.config.js
# Deployed: npx playwright test --config=e2e/playwright.config.js
```

- [ ] **Step 5: Commit**

```bash
git add e2e/
git commit -m "test(e2e): Playwright smoke tests (landing + login error)"
```

---

# Final Self-Review

After completing all 27 tasks, verify:

- [ ] All `pytest` tests pass: `pytest tests/ -v`
- [ ] All E2E tests pass against deployed env
- [ ] Coverage check: `pytest --cov=backend/app/auth --cov=backend/app/client_portal --cov-report=term-missing`
- [ ] Security checklist from spec §7.6 fully ticked
- [ ] `CORS_ALLOW_ORIGINS` set correctly in Render
- [ ] `RESEND_API_KEY` configured
- [ ] Manual smoke: create real test client, login, run STUB_ECHO, verify email arrives (use real email)
- [ ] Spec coverage: every section of the design doc has at least one task implementing it
