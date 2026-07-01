# Permisos de herramientas por usuario — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que el administrador otorgue, cuenta por cuenta, a qué herramientas del catálogo puede acceder cada cliente del portal, y que el portal solo muestre y ejecute las herramientas concedidas.

**Architecture:** Tabla nueva `user_tool_entitlements` (una fila por herramienta concedida a un `user_id`). Un servicio fino la consulta/actualiza. El catálogo del portal (`GET /client/catalog`) y la creación de jobs (`POST /client/tools/{code}/jobs`) filtran/validan por esas concesiones. Un backfill de una sola vez concede la sección Tributarias a los clientes ya existentes. La UI del Command Center (componente `Users`) gana un botón "Permisos" por cuenta que abre un panel con toggles por sección/herramienta.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 (backend), pytest (TestClient sobre la app legacy), React/Vite (frontend admin `frontend/`), sin Alembic (tablas por `Base.metadata.create_all`).

**Convención de comandos:** todos los `pytest` se ejecutan desde el directorio `auditbrain-python-runner/` (donde vive `app.py` y `tests/`). Ejemplo: `cd auditbrain-python-runner && python -m pytest ...`.

---

## Mapa de archivos

| Acción | Archivo | Responsabilidad |
|--------|---------|-----------------|
| Crear modelo `UserToolEntitlement` | `backend/app/auth/models.py` | Tabla `user_tool_entitlements` |
| Crear servicio | `backend/app/client_portal/entitlements.py` | `can_access_tool`, `list_user_tool_codes`, `set_user_entitlements`, `backfill_tributarias` |
| Wire backfill | `backend/app/db/session.py` | Llamar backfill idempotente tras `create_all` |
| Endpoints admin | `backend/app/staff_portal/router.py` | `GET /staff/tools`, `GET/PUT /staff/portal-users/{id}/entitlements` |
| Gating catálogo + 403 job | `backend/app/client_portal/router.py` | Filtrar catálogo por usuario; 403 al crear job sin permiso |
| API frontend | `frontend/src/api.js` | `getStaffTools`, `getUserEntitlements`, `setUserEntitlements` |
| UI permisos | `frontend/src/App.jsx` | Botón "Permisos" + panel con toggles |
| Tests | `tests/test_entitlements_*.py` | Servicio, endpoints, gating, backfill |
| Actualizar test existente | `tests/test_client_portal_jobs.py` | Ajustar a deny-by-default |

---

## Task 1: Modelo `UserToolEntitlement`

**Files:**
- Modify: `backend/app/auth/models.py` (agregar clase al final, tras `ClientDevice`)
- Test: `tests/test_entitlements_model.py`

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/test_entitlements_model.py`:

```python
"""Tabla user_tool_entitlements: creación y unicidad (user_id, tool_code)."""
import uuid
import pytest
from sqlalchemy.exc import IntegrityError
from backend.app.auth.models import Role, User, UserToolEntitlement
from backend.app.auth.service import create_user, get_user_by_email
from backend.app.db.session import SessionLocal


@pytest.fixture()
def db_session():
    db = SessionLocal()
    yield db
    db.close()


def _client_user(db):
    email = f"ent-{uuid.uuid4().hex[:8]}@example.com"
    return get_user_by_email(db, email) or create_user(
        db, email=email, password="x", role=Role.client
    )


def test_can_insert_entitlement(db_session):
    u = _client_user(db_session)
    ent = UserToolEntitlement(user_id=u.id, tool_code="ICT_2025", enabled=True)
    db_session.add(ent)
    db_session.commit()
    db_session.refresh(ent)
    assert ent.id is not None
    assert ent.enabled is True


def test_unique_user_tool(db_session):
    u = _client_user(db_session)
    db_session.add(UserToolEntitlement(user_id=u.id, tool_code="ICT_2025"))
    db_session.commit()
    db_session.add(UserToolEntitlement(user_id=u.id, tool_code="ICT_2025"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
```

- [ ] **Step 2: Correr el test y verlo fallar**

Run: `cd auditbrain-python-runner && python -m pytest tests/test_entitlements_model.py -v`
Expected: FAIL con `ImportError: cannot import name 'UserToolEntitlement'`.

- [ ] **Step 3: Implementar el modelo**

En `backend/app/auth/models.py`, agregar al final del archivo (después de `ClientDevice`). Nota: `UniqueConstraint` debe importarse en la línea de imports de `sqlalchemy`:

Cambiar la línea de import existente:
```python
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String
```
por:
```python
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
```

Y agregar la clase al final:
```python
class UserToolEntitlement(Base):
    """Permiso de una cuenta de portal (rol client) para acceder a una
    herramienta del catálogo. Una fila = una herramienta concedida."""

    __tablename__ = "user_tool_entitlements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    tool_code: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("user_id", "tool_code", name="uq_entitle_user_tool"),
    )
```

- [ ] **Step 4: Correr el test y verlo pasar**

Run: `cd auditbrain-python-runner && python -m pytest tests/test_entitlements_model.py -v`
Expected: PASS (2 passed). La tabla se crea vía `Base.metadata.create_all` al iniciar la app en el TestClient.

- [ ] **Step 5: Commit**

```bash
git add backend/app/auth/models.py tests/test_entitlements_model.py
git commit -m "feat(entitlements): modelo UserToolEntitlement (tabla user_tool_entitlements)"
```

---

## Task 2: Servicio de entitlements

**Files:**
- Create: `backend/app/client_portal/entitlements.py`
- Test: `tests/test_entitlements_service.py`

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/test_entitlements_service.py`:

```python
"""Servicio de entitlements: set/list/can_access."""
import uuid
import pytest
from backend.app.auth.models import Role
from backend.app.auth.service import create_user, get_user_by_email
from backend.app.client_portal import entitlements as ent
from backend.app.db.session import SessionLocal


@pytest.fixture()
def db_session():
    db = SessionLocal()
    yield db
    db.close()


def _client_user(db):
    email = f"entsvc-{uuid.uuid4().hex[:8]}@example.com"
    return get_user_by_email(db, email) or create_user(
        db, email=email, password="x", role=Role.client
    )


def test_default_no_access(db_session):
    u = _client_user(db_session)
    assert ent.list_user_tool_codes(db_session, u.id) == set()
    assert ent.can_access_tool(db_session, u.id, "ICT_2025") is False


def test_set_grants_only_valid_codes(db_session):
    u = _client_user(db_session)
    ent.set_user_entitlements(db_session, u.id, {"ICT_2025", "NO_EXISTE"})
    codes = ent.list_user_tool_codes(db_session, u.id)
    assert codes == {"ICT_2025"}  # código inexistente ignorado
    assert ent.can_access_tool(db_session, u.id, "ICT_2025") is True


def test_set_replaces_full_set(db_session):
    u = _client_user(db_session)
    ent.set_user_entitlements(db_session, u.id, {"ICT_2025"})
    ent.set_user_entitlements(db_session, u.id, set())  # revoca todo
    assert ent.list_user_tool_codes(db_session, u.id) == set()
    assert ent.can_access_tool(db_session, u.id, "ICT_2025") is False


def test_set_is_idempotent(db_session):
    u = _client_user(db_session)
    ent.set_user_entitlements(db_session, u.id, {"ICT_2025"})
    ent.set_user_entitlements(db_session, u.id, {"ICT_2025"})
    assert ent.list_user_tool_codes(db_session, u.id) == {"ICT_2025"}
```

- [ ] **Step 2: Correr el test y verlo fallar**

Run: `cd auditbrain-python-runner && python -m pytest tests/test_entitlements_service.py -v`
Expected: FAIL con `ModuleNotFoundError: backend.app.client_portal.entitlements`.

- [ ] **Step 3: Implementar el servicio**

Crear `backend/app/client_portal/entitlements.py`:

```python
"""Servicio de permisos herramienta↔usuario (gating comercial del portal).

Una cuenta de portal (rol client) solo puede ver/ejecutar las herramientas
que tenga concedidas aquí. El set se administra desde el Command Center.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.auth.models import UserToolEntitlement
from backend.app.client_portal.tool_registry import TOOLS


def list_user_tool_codes(db: Session, user_id: int) -> set[str]:
    """Códigos de herramienta habilitados para el usuario."""
    rows = db.execute(
        select(UserToolEntitlement.tool_code).where(
            UserToolEntitlement.user_id == user_id,
            UserToolEntitlement.enabled.is_(True),
        )
    ).scalars()
    return set(rows)


def can_access_tool(db: Session, user_id: int, tool_code: str) -> bool:
    """True si el usuario tiene la herramienta concedida y habilitada."""
    row = db.execute(
        select(UserToolEntitlement.id).where(
            UserToolEntitlement.user_id == user_id,
            UserToolEntitlement.tool_code == tool_code,
            UserToolEntitlement.enabled.is_(True),
        )
    ).first()
    return row is not None


def set_user_entitlements(db: Session, user_id: int, tool_codes: set[str]) -> None:
    """Reemplaza el conjunto completo de herramientas del usuario.

    - Ignora códigos que no existen en el registry.
    - Inserta/habilita las del set; borra las filas que ya no están en el set.
    """
    valid = {c for c in tool_codes if c in TOOLS}
    existing = {
        e.tool_code: e
        for e in db.execute(
            select(UserToolEntitlement).where(
                UserToolEntitlement.user_id == user_id
            )
        ).scalars()
    }
    for code in valid:
        if code in existing:
            existing[code].enabled = True
        else:
            db.add(UserToolEntitlement(user_id=user_id, tool_code=code, enabled=True))
    for code, row in existing.items():
        if code not in valid:
            db.delete(row)
    db.commit()
```

- [ ] **Step 4: Correr el test y verlo pasar**

Run: `cd auditbrain-python-runner && python -m pytest tests/test_entitlements_service.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/client_portal/entitlements.py tests/test_entitlements_service.py
git commit -m "feat(entitlements): servicio set/list/can_access"
```

---

## Task 3: Backfill de Tributarias a clientes existentes

**Files:**
- Modify: `backend/app/client_portal/entitlements.py` (agregar `backfill_tributarias`)
- Modify: `backend/app/db/session.py` (llamar backfill dentro de `init_db`)
- Test: `tests/test_entitlements_backfill.py`

**Decisión de idempotencia:** el backfill corre solo cuando la tabla
`user_tool_entitlements` está **globalmente vacía**. Así: en el primer arranque
tras el deploy (56 clientes, 0 filas) se conceden las herramientas de la sección
`TRIBUTARIAS` a todos los clientes; en adelante la tabla ya no está vacía y nunca
se re-aplica. Un cliente creado después (sin filas) arranca sin acceso
(deny-by-default), que es justamente lo deseado.

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/test_entitlements_backfill.py`:

```python
"""Backfill: concede la sección Tributarias a clientes sin entitlements
cuando la tabla está globalmente vacía; idempotente en el segundo arranque."""
import uuid
import pytest
from sqlalchemy import delete
from backend.app.auth.models import Role, UserToolEntitlement
from backend.app.auth.service import create_user, get_user_by_email
from backend.app.client_portal import entitlements as ent
from backend.app.client_portal.tool_registry import TOOLS
from backend.app.db.session import SessionLocal


@pytest.fixture()
def db_session():
    db = SessionLocal()
    yield db
    db.close()


def _tributarias_codes():
    return {c for c, t in TOOLS.items() if t.category == "TRIBUTARIAS" and t.enabled}


def test_backfill_grants_tributarias_when_table_empty(db_session):
    # Estado controlado: vaciar la tabla y crear un cliente sin entitlements.
    db_session.execute(delete(UserToolEntitlement))
    db_session.commit()
    email = f"bf-{uuid.uuid4().hex[:8]}@example.com"
    u = get_user_by_email(db_session, email) or create_user(
        db_session, email=email, password="x", role=Role.client
    )

    granted = ent.backfill_tributarias(db_session)

    assert granted >= 1
    assert ent.list_user_tool_codes(db_session, u.id) == _tributarias_codes()


def test_backfill_noop_when_table_not_empty(db_session):
    # Con al menos una fila, el backfill no debe tocar nada.
    db_session.execute(delete(UserToolEntitlement))
    db_session.commit()
    email = f"bf2-{uuid.uuid4().hex[:8]}@example.com"
    u = create_user(db_session, email=email, password="x", role=Role.client)
    ent.set_user_entitlements(db_session, u.id, {"ICT_2025"})  # deja 1 fila

    email2 = f"bf3-{uuid.uuid4().hex[:8]}@example.com"
    u2 = create_user(db_session, email=email2, password="x", role=Role.client)

    granted = ent.backfill_tributarias(db_session)

    assert granted == 0  # tabla no vacía → no corre
    assert ent.list_user_tool_codes(db_session, u2.id) == set()  # u2 sigue sin nada
```

- [ ] **Step 2: Correr el test y verlo fallar**

Run: `cd auditbrain-python-runner && python -m pytest tests/test_entitlements_backfill.py -v`
Expected: FAIL con `AttributeError: module ... has no attribute 'backfill_tributarias'`.

- [ ] **Step 3: Implementar el backfill**

Agregar a `backend/app/client_portal/entitlements.py` (imports adicionales arriba y función al final):

Al inicio, ampliar imports:
```python
from backend.app.auth.models import Role, User, UserToolEntitlement
```

Función nueva:
```python
def backfill_tributarias(db: Session) -> int:
    """Concede las herramientas de la sección TRIBUTARIAS a todas las cuentas
    de rol client, SOLO si la tabla de entitlements está globalmente vacía.
    Devuelve el número de concesiones creadas (0 si no corrió)."""
    already = db.execute(select(UserToolEntitlement.id).limit(1)).first()
    if already is not None:
        return 0  # ya inicializado; nunca re-aplicar

    trib_codes = [
        code for code, t in TOOLS.items()
        if t.category == "TRIBUTARIAS" and t.enabled
    ]
    if not trib_codes:
        return 0

    client_ids = db.execute(
        select(User.id).where(User.role == Role.client)
    ).scalars().all()

    created = 0
    for uid in client_ids:
        for code in trib_codes:
            db.add(UserToolEntitlement(user_id=uid, tool_code=code, enabled=True))
            created += 1
    db.commit()
    return created
```

- [ ] **Step 4: Correr el test y verlo pasar**

Run: `cd auditbrain-python-runner && python -m pytest tests/test_entitlements_backfill.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Wire dentro de `init_db`**

En `backend/app/db/session.py`, dentro de `init_db()`, **al final de la función** (después de `create_all` y de las migraciones ALTER TABLE), agregar:

```python
    # Backfill de entitlements: concede la sección Tributarias a los clientes
    # existentes en el primer arranque tras activar el gating comercial.
    try:
        from backend.app.client_portal.entitlements import backfill_tributarias
        _bf_db = SessionLocal()
        try:
            backfill_tributarias(_bf_db)
        finally:
            _bf_db.close()
    except Exception:
        # El backfill nunca debe impedir el arranque de la app.
        pass
```

Nota: `SessionLocal` ya está definido en este módulo. Si `init_db` no lo tiene en scope, usar el símbolo del módulo directamente (está a nivel de módulo).

- [ ] **Step 6: Verificar que la app sigue arrancando (suite completa de auth/portal)**

Run: `cd auditbrain-python-runner && python -m pytest tests/test_entitlements_backfill.py tests/test_client_portal_login.py -v`
Expected: PASS (todos verdes). Confirma que el wire no rompe el arranque.

- [ ] **Step 7: Commit**

```bash
git add backend/app/client_portal/entitlements.py backend/app/db/session.py tests/test_entitlements_backfill.py
git commit -m "feat(entitlements): backfill Tributarias a clientes existentes (idempotente en init_db)"
```

---

## Task 4: Endpoints de administración (`/staff`)

**Files:**
- Modify: `backend/app/staff_portal/router.py` (agregar modelos y 3 endpoints al `global_router`)
- Test: `tests/test_entitlements_staff_endpoints.py`

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/test_entitlements_staff_endpoints.py`:

```python
"""Endpoints admin de entitlements: GET /staff/tools, GET/PUT entitlements."""
import uuid
import pytest
from backend.app.auth.models import Role
from backend.app.auth.service import create_user, get_user_by_email
from backend.app.auth.jwt_tokens import create_access_token
from backend.app.client_portal.service import create_portal_user
from backend.app.context.models import Organization, Client
from backend.app.db.session import SessionLocal


@pytest.fixture()
def db_session():
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture()
def admin_token(db_session):
    email = f"admin-ent-{uuid.uuid4().hex[:8]}@example.com"
    u = get_user_by_email(db_session, email) or create_user(
        db_session, email=email, password="x", role=Role.admin
    )
    return create_access_token(subject=u.email, role="admin")


@pytest.fixture()
def portal_user(db_session):
    suffix = uuid.uuid4().hex[:8]
    org = Organization(name=f"ACG-ent-{suffix}", slug=f"acg-ent-{suffix}", is_active=True)
    db_session.add(org); db_session.commit(); db_session.refresh(org)
    cli = Client(organization_id=org.id, name=f"CL-ent-{suffix}", is_active=True)
    db_session.add(cli); db_session.commit(); db_session.refresh(cli)
    user, _ = create_portal_user(db_session, client_id=cli.id, email=f"pu-{suffix}@example.com")
    return user


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def test_staff_tools_lists_catalog(client, admin_token):
    r = client.get("/api/v1/staff/tools", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    cats = {c["id"]: c for c in r.json()}
    assert "TRIBUTARIAS" in cats
    assert "TESTING" not in cats  # categoría interna no se expone
    codes = [t["code"] for t in cats["TRIBUTARIAS"]["tools"]]
    assert "ICT_2025" in codes


def test_get_and_put_entitlements(client, admin_token, portal_user):
    # Estado inicial: sin nada
    r = client.get(
        f"/api/v1/staff/portal-users/{portal_user.id}/entitlements",
        headers=_h(admin_token),
    )
    assert r.status_code == 200
    assert r.json()["enabled_tool_codes"] == []

    # Conceder ICT_2025
    r2 = client.put(
        f"/api/v1/staff/portal-users/{portal_user.id}/entitlements",
        json={"tool_codes": ["ICT_2025"]},
        headers=_h(admin_token),
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["enabled_tool_codes"] == ["ICT_2025"]

    # Revocar todo
    r3 = client.put(
        f"/api/v1/staff/portal-users/{portal_user.id}/entitlements",
        json={"tool_codes": []},
        headers=_h(admin_token),
    )
    assert r3.json()["enabled_tool_codes"] == []


def test_entitlements_404_for_unknown_user(client, admin_token):
    r = client.get(
        "/api/v1/staff/portal-users/99999999/entitlements",
        headers=_h(admin_token),
    )
    assert r.status_code == 404


def test_entitlements_requires_admin(client, db_session, portal_user):
    email = f"op-{uuid.uuid4().hex[:8]}@example.com"
    u = create_user(db_session, email=email, password="x", role=Role.user)
    token = create_access_token(subject=u.email, role="user")
    r = client.get(
        f"/api/v1/staff/portal-users/{portal_user.id}/entitlements",
        headers=_h(token),
    )
    assert r.status_code == 403
```

- [ ] **Step 2: Correr el test y verlo fallar**

Run: `cd auditbrain-python-runner && python -m pytest tests/test_entitlements_staff_endpoints.py -v`
Expected: FAIL (404 en `/staff/tools` porque el endpoint no existe todavía).

- [ ] **Step 3: Implementar modelos y endpoints**

En `backend/app/staff_portal/router.py`, agregar los modelos Pydantic junto a los otros (después de `class PortalUserOut`):

```python
class ToolLite(BaseModel):
    code: str
    label: str
    description: str


class CategoryTools(BaseModel):
    id: str
    label: str
    tools: list[ToolLite]


class EntitlementsOut(BaseModel):
    user_id: int
    enabled_tool_codes: list[str]


class SetEntitlementsRequest(BaseModel):
    tool_codes: list[str]
```

Y agregar los 3 endpoints al final del archivo (usan `global_router`, `require_admin`, `_require_portal_user` y `get_db`, todos ya presentes):

```python
@global_router.get(
    "/tools",
    response_model=list[CategoryTools],
    dependencies=[Depends(require_admin)],
)
def list_all_tools_for_admin():
    """Catálogo COMPLETO (todas las categorías visibles + sus herramientas
    habilitadas) para pintar la pantalla de permisos. Excluye TESTING porque
    no está en CATEGORIES."""
    from backend.app.client_portal.tool_registry import CATEGORIES, TOOLS

    out: list[CategoryTools] = []
    for c in CATEGORIES:
        tools = [
            ToolLite(code=t.code, label=t.label, description=t.description)
            for t in TOOLS.values()
            if t.category == c["id"] and t.enabled
        ]
        out.append(CategoryTools(id=c["id"], label=c["label"], tools=tools))
    return out


@global_router.get(
    "/portal-users/{user_id}/entitlements",
    response_model=EntitlementsOut,
    dependencies=[Depends(require_admin)],
)
def get_user_entitlements_endpoint(user_id: int, db: Session = Depends(get_db)):
    from backend.app.client_portal.entitlements import list_user_tool_codes

    user = _require_portal_user(db, user_id)
    return EntitlementsOut(
        user_id=user.id,
        enabled_tool_codes=sorted(list_user_tool_codes(db, user.id)),
    )


@global_router.put(
    "/portal-users/{user_id}/entitlements",
    response_model=EntitlementsOut,
    dependencies=[Depends(require_admin)],
)
def set_user_entitlements_endpoint(
    user_id: int,
    body: SetEntitlementsRequest,
    db: Session = Depends(get_db),
):
    from backend.app.client_portal.entitlements import (
        list_user_tool_codes,
        set_user_entitlements,
    )

    user = _require_portal_user(db, user_id)
    set_user_entitlements(db, user.id, set(body.tool_codes))
    return EntitlementsOut(
        user_id=user.id,
        enabled_tool_codes=sorted(list_user_tool_codes(db, user.id)),
    )
```

- [ ] **Step 4: Correr el test y verlo pasar**

Run: `cd auditbrain-python-runner && python -m pytest tests/test_entitlements_staff_endpoints.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/staff_portal/router.py tests/test_entitlements_staff_endpoints.py
git commit -m "feat(entitlements): endpoints admin GET /staff/tools + GET/PUT entitlements"
```

---

## Task 5: Filtrar `GET /client/catalog` por usuario

**Files:**
- Modify: `backend/app/client_portal/router.py` (endpoint `get_catalog`, ~línea 361)
- Modify: `tests/test_client_portal_jobs.py` (ajustar test existente a deny-by-default)
- Test: `tests/test_entitlements_catalog_gating.py`

- [ ] **Step 1: Escribir el test nuevo que falla**

Crear `tests/test_entitlements_catalog_gating.py`:

```python
"""El catálogo del portal filtra por los entitlements del usuario."""
import uuid
import pytest
from backend.app.client_portal.service import create_portal_user
from backend.app.client_portal import entitlements as ent
from backend.app.context.models import Organization, Client
from backend.app.db.session import SessionLocal


@pytest.fixture()
def db_session():
    db = SessionLocal()
    yield db
    db.close()


def _login(client, db, granted):
    suffix = uuid.uuid4().hex[:8]
    org = Organization(name=f"ACG-gate-{suffix}", slug=f"acg-gate-{suffix}", is_active=True)
    db.add(org); db.commit(); db.refresh(org)
    cli = Client(organization_id=org.id, name=f"CL-gate-{suffix}", is_active=True)
    db.add(cli); db.commit(); db.refresh(cli)
    user, pwd = create_portal_user(db, client_id=cli.id, email=f"gate-{suffix}@example.com")
    if granted:
        ent.set_user_entitlements(db, user.id, set(granted))
    r = client.post("/api/v1/client/auth/login", data={"username": user.email, "password": pwd})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    device_id = r.cookies.get("device_id")
    return {"headers": {"Authorization": f"Bearer {token}"},
            "cookies": {"device_id": device_id} if device_id else {}}


def _codes_by_cat(body):
    return {c["id"]: [t["code"] for t in c["tools"]] for c in body["categories"]}


def test_catalog_hides_tools_without_entitlement(client, db_session):
    auth = _login(client, db_session, granted=set())
    r = client.get("/api/v1/client/catalog", **auth)
    assert r.status_code == 200
    by_cat = _codes_by_cat(r.json())
    # Las categorías siguen presentes (para la sidebar) pero sin herramientas
    assert "TRIBUTARIAS" in by_cat
    assert by_cat["TRIBUTARIAS"] == []


def test_catalog_shows_only_granted_tool(client, db_session):
    auth = _login(client, db_session, granted={"ICT_2025"})
    r = client.get("/api/v1/client/catalog", **auth)
    assert r.status_code == 200
    by_cat = _codes_by_cat(r.json())
    assert by_cat["TRIBUTARIAS"] == ["ICT_2025"]
```

- [ ] **Step 2: Correr el test y verlo fallar**

Run: `cd auditbrain-python-runner && python -m pytest tests/test_entitlements_catalog_gating.py -v`
Expected: FAIL — `test_catalog_hides_tools_without_entitlement` falla porque hoy el catálogo devuelve ICT_2025 a todos.

- [ ] **Step 3: Implementar el filtrado**

En `backend/app/client_portal/router.py`, reemplazar el endpoint `get_catalog` (actualmente ~líneas 361-396) por:

```python
@router.get("/catalog", response_model=ClientCatalogResponse)
def get_catalog(
    user: User = Depends(require_client_with_device),
    db: Session = Depends(get_db),
):
    """Catálogo filtrado por los permisos (entitlements) del usuario.
    Las categorías se devuelven todas (para la barra lateral); solo se incluyen
    las herramientas concedidas al usuario. Sin permisos → categorías vacías
    ('Próximamente')."""
    from backend.app.client_portal.entitlements import list_user_tool_codes

    allowed = list_user_tool_codes(db, user.id)

    tools_by_cat: dict[str, list] = {c["id"]: [] for c in CATEGORIES}
    for t in list_enabled_tools():
        if t.code not in allowed:
            continue
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
            CategoryOut(
                id=c["id"],
                label=c["label"],
                description=c.get("description"),
                tools=tools_by_cat.get(c["id"], []),
            )
            for c in CATEGORIES
        ]
    )
```

Verificar que el import de `get_db` ya exista al inicio del archivo (se usa en otros endpoints del mismo router, p. ej. `create_client_job_endpoint`). No hace falta agregarlo.

- [ ] **Step 4: Correr el test nuevo y verlo pasar**

Run: `cd auditbrain-python-runner && python -m pytest tests/test_entitlements_catalog_gating.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Actualizar el test existente a deny-by-default**

En `tests/test_client_portal_jobs.py`, el test `test_catalog_returns_categories_with_stub_tool` asume que el cliente ve ICT_2025 sin permisos. Ajustarlo para conceder primero. Reemplazar la función completa por:

```python
def test_catalog_returns_categories_with_stub_tool(client, logged_client, db_session):
    """Con gating: tras conceder ICT_2025 al cliente, el catálogo lo muestra en
    TRIBUTARIAS. Las 4 categorías de cara al cliente siguen presentes y TESTING
    nunca se expone."""
    from backend.app.client_portal import entitlements as ent
    ent.set_user_entitlements(db_session, logged_client["user"].id, {"ICT_2025"})

    r = client.get(
        "/api/v1/client/catalog",
        headers=logged_client["headers"],
        cookies=logged_client["cookies"],
    )
    assert r.status_code == 200
    body = r.json()
    cats = {c["id"]: c for c in body["categories"]}
    for expected in ("TRIBUTARIAS", "NIIF", "LABORALES", "SOCIETARIAS"):
        assert expected in cats, f"Falta categoría {expected}"
    trib_codes = [t["code"] for t in cats["TRIBUTARIAS"]["tools"]]
    assert "ICT_2025" in trib_codes
    assert "TESTING" not in cats
```

- [ ] **Step 6: Correr el test existente ajustado y verlo pasar**

Run: `cd auditbrain-python-runner && python -m pytest tests/test_client_portal_jobs.py::test_catalog_returns_categories_with_stub_tool -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/client_portal/router.py tests/test_entitlements_catalog_gating.py tests/test_client_portal_jobs.py
git commit -m "feat(entitlements): filtrar /client/catalog por permisos del usuario"
```

---

## Task 6: Enforcement 403 al crear job

**Files:**
- Modify: `backend/app/client_portal/router.py` (`create_client_job_endpoint`, ~línea 239)
- Test: `tests/test_entitlements_job_enforcement.py`

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/test_entitlements_job_enforcement.py`:

```python
"""Crear un job de una herramienta NO concedida devuelve 403."""
import io
import uuid
import pytest
from backend.app.client_portal.service import create_portal_user
from backend.app.client_portal import entitlements as ent
from backend.app.context.models import Organization, Client
from backend.app.db.session import SessionLocal


@pytest.fixture()
def db_session():
    db = SessionLocal()
    yield db
    db.close()


def _login(client, db, granted):
    suffix = uuid.uuid4().hex[:8]
    org = Organization(name=f"ACG-job-{suffix}", slug=f"acg-job-{suffix}", is_active=True)
    db.add(org); db.commit(); db.refresh(org)
    cli = Client(organization_id=org.id, name=f"CL-job-{suffix}", is_active=True)
    db.add(cli); db.commit(); db.refresh(cli)
    user, pwd = create_portal_user(db, client_id=cli.id, email=f"job-{suffix}@example.com")
    if granted:
        ent.set_user_entitlements(db, user.id, set(granted))
    r = client.post("/api/v1/client/auth/login", data={"username": user.email, "password": pwd})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    device_id = r.cookies.get("device_id")
    return {"headers": {"Authorization": f"Bearer {token}"},
            "cookies": {"device_id": device_id} if device_id else {}}


def test_job_denied_without_entitlement(client, db_session):
    auth = _login(client, db_session, granted=set())
    r = client.post(
        "/api/v1/client/tools/STUB_ECHO/jobs",
        files={"input": ("x.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
        **auth,
    )
    assert r.status_code == 403, r.text


def test_job_allowed_with_entitlement(client, db_session):
    auth = _login(client, db_session, granted={"STUB_ECHO"})
    r = client.post(
        "/api/v1/client/tools/STUB_ECHO/jobs",
        files={"input": ("x.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
        **auth,
    )
    assert r.status_code == 201, r.text
```

- [ ] **Step 2: Correr el test y verlo fallar**

Run: `cd auditbrain-python-runner && python -m pytest tests/test_entitlements_job_enforcement.py -v`
Expected: FAIL — `test_job_denied_without_entitlement` da 201 en vez de 403 (aún no hay validación).

- [ ] **Step 3: Implementar el 403**

En `backend/app/client_portal/router.py`, dentro de `create_client_job_endpoint`, justo después del bloque `try/except KeyError` que resuelve `tool` (líneas ~250-253), agregar:

```python
    # Enforcement de permiso: el cliente solo ejecuta lo que tiene concedido.
    from backend.app.client_portal.entitlements import can_access_tool
    if not can_access_tool(db, user.id, tool_code):
        raise HTTPException(
            403,
            detail="No tienes acceso a esta herramienta. Contacta a tu administrador.",
        )
```

- [ ] **Step 4: Correr el test y verlo pasar**

Run: `cd auditbrain-python-runner && python -m pytest tests/test_entitlements_job_enforcement.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/client_portal/router.py tests/test_entitlements_job_enforcement.py
git commit -m "feat(entitlements): 403 al crear job de herramienta no concedida"
```

---

## Task 7: Funciones API en el frontend admin

**Files:**
- Modify: `frontend/src/api.js` (agregar 3 funciones exportadas)

No hay suite de tests JS en el repo; la verificación de esta task es la
compilación/uso desde el componente (Task 8) y la verificación empírica (Task 9).

- [ ] **Step 1: Implementar las funciones**

En `frontend/src/api.js`, agregar (por ejemplo al final del archivo). Usan los
helpers existentes `parse()` y `authHeaders()`:

```javascript
// ---- Permisos de herramientas por usuario (entitlements) ----
export async function getStaffTools() {
  return parse(
    await fetch(`${API_BASE}/api/v1/staff/tools`, { headers: authHeaders() })
  );
}

export async function getUserEntitlements(userId) {
  return parse(
    await fetch(`${API_BASE}/api/v1/staff/portal-users/${userId}/entitlements`, {
      headers: authHeaders(),
    })
  );
}

export async function setUserEntitlements(userId, toolCodes) {
  return parse(
    await fetch(`${API_BASE}/api/v1/staff/portal-users/${userId}/entitlements`, {
      method: "PUT",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ tool_codes: toolCodes }),
    })
  );
}
```

- [ ] **Step 2: Verificar que el build no rompe**

Run: `cd auditbrain-python-runner/frontend && npm run build`
Expected: build exitoso (sin errores de sintaxis). Si `npm ci` no se ha corrido, ejecutarlo primero.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api.js
git commit -m "feat(entitlements): funciones API frontend getStaffTools/get+setUserEntitlements"
```

---

## Task 8: Panel de permisos en el componente `Users`

**Files:**
- Modify: `frontend/src/App.jsx` (componente `Users`: estado + botón "Permisos" + panel)

**Diseño de UI:** al hacer clic en "Permisos" de una cuenta, se abre un panel
(reutilizando `Panel`) con las secciones y sus herramientas como checkboxes.
Botón Guardar → `setUserEntitlements`. Botón Cerrar. Reutiliza el tema oscuro
existente; no se introduce librería nueva.

- [ ] **Step 1: Importar las nuevas funciones API**

En `frontend/src/App.jsx`, en el import de `api` (buscar `import * as api` o el import nombrado que ya usa `api.listAllPortalUsers`), no hace falta cambiar nada si se usa el namespace `api.*`. Las funciones nuevas se llaman como `api.getStaffTools()`, `api.getUserEntitlements()`, `api.setUserEntitlements()`.

- [ ] **Step 2: Agregar estado en el componente `Users`**

Dentro de `function Users()` (junto a los otros `useState`, cerca de la línea 388), agregar:

```javascript
  // Panel de permisos de herramientas por cuenta
  const [permUser, setPermUser] = useState(null);   // { id, email, cliente }
  const [permCats, setPermCats] = useState([]);      // catálogo completo
  const [permSel, setPermSel] = useState(new Set()); // códigos activos
  const [permBusy, setPermBusy] = useState(false);
  const [permErr, setPermErr] = useState("");

  async function openPerms(u) {
    setPermErr(""); setPermUser(u); setPermSel(new Set()); setPermCats([]);
    try {
      const [cats, ent] = await Promise.all([
        api.getStaffTools(),
        api.getUserEntitlements(u.id),
      ]);
      setPermCats(cats);
      setPermSel(new Set(ent.enabled_tool_codes));
    } catch (e) { setPermErr(e.message); }
  }
  function togglePerm(code) {
    setPermSel((prev) => {
      const next = new Set(prev);
      if (next.has(code)) next.delete(code); else next.add(code);
      return next;
    });
  }
  async function savePerms() {
    setPermBusy(true); setPermErr("");
    try {
      await api.setUserEntitlements(permUser.id, Array.from(permSel));
      setPermUser(null);
    } catch (e) { setPermErr(e.message); }
    finally { setPermBusy(false); }
  }
```

- [ ] **Step 3: Agregar el botón "Permisos" en la fila de cada cuenta**

En el render de "Todas las cuentas de cliente" (línea ~751-758), agregar un botón antes de "Resetear":

```javascript
                  <span style={{ display: "flex", gap: 8 }}>
                    <button className="btn" onClick={() => openPerms(u)}>Permisos</button>
                    <button className="btn" onClick={() => resetGlobal(u)}>Resetear</button>
                    <button className="btn" onClick={() => toggleGlobal(u)}>
                      {u.is_active ? "Deshabilitar" : "Habilitar"}
                    </button>
                    <button className="btn" style={{ color: "var(--danger)", borderColor: "var(--danger)" }}
                      onClick={() => deleteGlobal(u)}>Borrar</button>
                  </span>
```

- [ ] **Step 4: Renderizar el panel de permisos**

Justo después del `<ViewHead ... />` (línea ~542), agregar el panel condicional:

```javascript
      {permUser && (
        <Panel title={`🔐 Permisos · ${permUser.email}`} max={680}>
          <p className="muted" style={{ marginTop: 0 }}>
            Empresa: <b>{permUser.cliente}</b>. Marca las herramientas a las que
            esta cuenta puede acceder.
          </p>
          {permErr && <p style={{ color: "var(--danger)" }}>{permErr}</p>}
          {permCats.length === 0 && !permErr && <p className="muted">Cargando…</p>}
          {permCats.map((cat) => (
            <div key={cat.id} style={{ marginBottom: 14 }}>
              <div style={{ fontWeight: 600, margin: "8px 0 4px" }}>
                <span className="pc-code" style={{ marginRight: 8 }}>{cat.id.slice(0, 4)}</span>
                {cat.label}
              </div>
              {cat.tools.length === 0 ? (
                <p className="muted" style={{ margin: "2px 0 0 8px" }}>Sin herramientas aún.</p>
              ) : (
                cat.tools.map((t) => (
                  <label key={t.code} style={{ display: "flex", alignItems: "center",
                    gap: 8, padding: "4px 0 4px 8px" }}>
                    <input
                      type="checkbox"
                      checked={permSel.has(t.code)}
                      onChange={() => togglePerm(t.code)}
                    />
                    <span>{t.label}</span>
                  </label>
                ))
              )}
            </div>
          ))}
          <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
            <button className="btn primary" onClick={savePerms} disabled={permBusy}>
              {permBusy ? "Guardando…" : "Guardar permisos"}
            </button>
            <button className="btn" onClick={() => setPermUser(null)} disabled={permBusy}>
              Cerrar
            </button>
          </div>
        </Panel>
      )}
```

Nota: `Panel` y la clase `pc-code`/`btn primary` ya existen en el proyecto.
Si `pc-code` no aplica estilo en este frontend (es del portal cliente), usar
`<b>{cat.id.slice(0,4)}</b>`; verificar visualmente en Task 9.

- [ ] **Step 5: Verificar que el build compila**

Run: `cd auditbrain-python-runner/frontend && npm run build`
Expected: build exitoso.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/App.jsx
git commit -m "feat(entitlements): panel de permisos por cuenta en Command Center"
```

---

## Task 9: Verificación integral + deploy

**Files:** ninguno (verificación y despliegue).

- [ ] **Step 1: Correr TODA la suite de entitlements + portal + staff**

Run:
```bash
cd auditbrain-python-runner && python -m pytest \
  tests/test_entitlements_model.py \
  tests/test_entitlements_service.py \
  tests/test_entitlements_backfill.py \
  tests/test_entitlements_staff_endpoints.py \
  tests/test_entitlements_catalog_gating.py \
  tests/test_entitlements_job_enforcement.py \
  tests/test_client_portal_jobs.py \
  tests/test_client_portal_login.py \
  tests/test_staff_client_admin.py \
  -v
```
Expected: TODOS verdes. Si algo falla, arreglar antes de continuar (regla suprema del CLAUDE.md: no entregar sin verificar).

- [ ] **Step 2: Correr la suite completa para descartar regresiones**

Run: `cd auditbrain-python-runner && python -m pytest tests/ --tb=short -q`
Expected: sin regresiones nuevas. Nota: el CLAUDE.md documenta 5 tests legacy pre-existentes que fallan (`test_chat.py::...inaccessible_project...`, `test_context.py::...` x3, `test_sandbox.py::test_make_rlimit_preexec_optin`) — esos NO cuentan como regresión. Cualquier OTRO fallo sí.

- [ ] **Step 3: Verificación empírica local del gating (script manual)**

Con la app corriendo localmente (o vía TestClient en un `python -c`), confirmar el flujo real:
1. Crear un cliente de portal, concederle solo `ICT_2025` vía `PUT /staff/portal-users/{id}/entitlements`.
2. `GET /client/catalog` como ese cliente → solo TRIBUTARIAS trae ICT_2025; el resto de categorías vacías.
3. Quitar el permiso (`PUT` con `[]`) → catálogo sin herramientas y `POST /client/tools/ICT_2025/jobs` → 403.

Documentar el resultado (pegar el output) en el PR/mensaje. NO afirmar "funciona" sin este output.

- [ ] **Step 4: Commit del plan como completado y push a main (deploy)**

El backend y el frontend admin tienen `autoDeploy: true` en `render.yaml`
(servicios `auditbrain-python-runner` y `auditbrain-frontend`). Deploy = push a `main`.

```bash
cd auditbrain-python-runner
git fetch origin main
# Verificar fast-forward limpio antes de empujar (ver patrón usado en la sesión).
git push origin HEAD:main
```

- [ ] **Step 5: Verificación post-deploy (empírica, en producción)**

1. Confirmar backend sano: `GET https://auditbrain-python-runner.onrender.com/api/v1/health` → 200.
2. En el Command Center (`auditbrain-frontend.onrender.com`), USR·Cuentas: abrir "Permisos" de una cuenta, confirmar que carga las secciones + herramientas y que Guardar persiste (reabrir y ver el estado).
3. Confirmar que los 56 clientes existentes conservan acceso a Tributarias (abrir Permisos de 2-3 cuentas y ver ICT_2025 marcado, resultado del backfill).
4. Iniciar sesión en el portal cliente con una cuenta y confirmar que solo ve lo concedido.

Reportar honestamente cualquier diferencia (regla suprema).

---

## Notas de verificación del plan (self-review)

- **Cobertura del spec:** modelo (T1), servicio (T2), backfill/default (T3), endpoints admin (T4), gating catálogo (T5), enforcement job/403 (T6), UI front (T7-T8), pruebas + verificación empírica + deploy (T9). Todas las secciones del spec tienen tarea.
- **Deny-by-default + no romper a los 56:** T3 (backfill Tributarias) + T5 (catálogo filtra) cubren esto; test dedicado en T3.
- **Rompimiento de test existente detectado:** `test_catalog_returns_categories_with_stub_tool` se actualiza explícitamente en T5 Step 5.
- **Consistencia de nombres:** `list_user_tool_codes`, `can_access_tool`, `set_user_entitlements`, `backfill_tributarias`, `UserToolEntitlement`, endpoints `/staff/tools` y `/staff/portal-users/{id}/entitlements` — usados idénticos en backend, tests y frontend.
