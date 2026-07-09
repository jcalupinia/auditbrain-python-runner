"""Tests del service layer (CRUD de ToolJob) del Informe de Cumplimiento
Tributario.

Nota de adaptación: el helper `_admin_and_project` del plan invocaba
`ctx_service.create_client`/`create_project` sin `organization_id`, pero en
este repo ambas funciones son multi-tenant y lo requieren (ver
`backend/app/context/service.py`). Se adapta siguiendo el patrón real usado
en `tests/test_aud_of_service.py::_mk_admin_project`
(`ensure_user_has_organization` + `organization_id=u.organization_id`).

Además, para el test de acceso cruzado, el segundo usuario NO puede crearse
como otro admin vía `_admin_and_project()`: como no existe una API de
"crear organización" separada en este helper, todo usuario sin
`organization_id` cae en la misma organización por defecto
(`ensure_user_has_organization` → `get_or_create_default_organization`), y un
admin de la MISMA organización SIEMPRE tiene acceso (bypass de membership).
Por eso el usuario "sin acceso" se crea como `Role.user` sin
`add_project_member`, igual que en `test_aud_of_service.py::test_create_job_no_access_raises`,
preservando la intención del test del plan (un usuario sin acceso al
proyecto no puede leer el job).

Por último, `_admin_and_project` devuelve `user_id` (no la instancia `User`)
siguiendo el mismo patrón de `test_aud_of_service.py`: la sesión que crea el
usuario se cierra dentro del helper, así que devolver la instancia `User`
directamente produce `DetachedInstanceError` al usarla en una sesión nueva.
Cada test reabre el usuario con `db.get(User, user_id)` en su propia sesión.
"""

import uuid

import pytest

from backend.app.auth import service as auth_service
from backend.app.auth.models import Role, User
from backend.app.aud.informe_cumplimiento_tributario import service
from backend.app.context import service as ctx_service
from backend.app.db.session import SessionLocal, init_db


@pytest.fixture(autouse=True)
def _db():
    init_db()
    yield


def _admin_and_project():
    db = SessionLocal()
    try:
        tag = uuid.uuid4().hex[:6]
        user = auth_service.create_user(
            db, email=f"a-{tag}@ex.com", password="Sup3rSecret!", role=Role.admin
        )
        user = ctx_service.ensure_user_has_organization(db, user)
        client = ctx_service.create_client(
            db, organization_id=user.organization_id, name=f"C-{tag}"
        )
        project = ctx_service.create_project(
            db, organization_id=user.organization_id, client_id=client.id,
            name=f"P-{tag}", module_code="AUD",
        )
        return user.id, project.id
    finally:
        db.close()


def test_create_and_get_job():
    user_id, pid = _admin_and_project()
    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        job = service.create_job(
            db, user=user, project_id=pid,
            cliente_name="AXXISGASTRO CIA. LTDA.", ejercicio="2025",
            firma_auditora="audit_consulting",
        )
        assert job.tool_code == service.TOOL_CODE
        assert job.status == "pending"
        got = service.get_job(db, user, job.id)
        assert got.id == job.id
    finally:
        db.close()


def test_get_job_sin_acceso_lanza_permissionerror():
    user_id, pid = _admin_and_project()
    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        job = service.create_job(
            db, user=user, project_id=pid,
            cliente_name="X", ejercicio="2025", firma_auditora="audit_consulting",
        )
        job_id = job.id
    finally:
        db.close()

    db = SessionLocal()
    try:
        other = auth_service.create_user(
            db, email=f"o-{uuid.uuid4().hex[:6]}@ex.com",
            password="Sup3rSecret!", role=Role.user,
        )
        other = ctx_service.ensure_user_has_organization(db, other)
        with pytest.raises(PermissionError):
            service.get_job(db, other, job_id)
    finally:
        db.close()
