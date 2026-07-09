"""Política: operadores (rol user) = admin salvo gestión de cuentas.

Verifica que un operador (rol user) ve y accede a TODOS los proyectos de su
organización (como el admin), aunque no sea ProjectMember; y que los guards de
rol siguen siendo correctos (require_staff acepta user, require_admin lo rechaza).
"""

import uuid

import pytest
from fastapi import HTTPException

from backend.app.auth import service as auth_service
from backend.app.auth.deps import require_admin, require_staff
from backend.app.auth.models import Role
from backend.app.context import service as ctx_service
from backend.app.db.session import SessionLocal, init_db


@pytest.fixture(autouse=True)
def _db():
    init_db()
    yield


def _seed_admin_project_and_operator():
    db = SessionLocal()
    try:
        tag = uuid.uuid4().hex[:6]
        admin = auth_service.create_user(
            db, email=f"adm-{tag}@ex.com", password="Sup3rSecret!", role=Role.admin
        )
        ctx_service.ensure_user_has_organization(db, admin)
        db.refresh(admin)
        client = ctx_service.create_client(
            db, name=f"C-{tag}", organization_id=admin.organization_id
        )
        proj = ctx_service.create_project(
            db, client_id=client.id, name=f"P-{tag}", module_code="AUD",
            organization_id=admin.organization_id,
        )
        operator = auth_service.create_user(
            db, email=f"op-{tag}@ex.com", password="Sup3rSecret!", role=Role.user
        )
        ctx_service.ensure_user_has_organization(db, operator)
        db.refresh(operator)
        return admin.id, operator.id, proj.id
    finally:
        db.close()


def test_operator_sees_and_accesses_all_org_projects():
    admin_id, operator_id, project_id = _seed_admin_project_and_operator()
    db = SessionLocal()
    try:
        from backend.app.auth.models import User
        from backend.app.context.models import Project

        operator = db.get(User, operator_id)
        admin = db.get(User, admin_id)
        project = db.get(Project, project_id)

        # Misma organización (política de firma: operadores en la org por defecto).
        assert operator.organization_id == admin.organization_id

        # El operador VE el proyecto aunque no sea ProjectMember (lo creó el admin).
        visible_ids = [p.id for p in ctx_service.list_user_projects(db, operator)]
        assert project.id in visible_ids

        # Y puede ACCEDER a él.
        assert ctx_service.user_can_access_project(db, operator, project) is True
    finally:
        db.close()


def test_role_guards():
    _admin_id, operator_id, _project_id = _seed_admin_project_and_operator()
    db = SessionLocal()
    try:
        from backend.app.auth.models import User

        operator = db.get(User, operator_id)
        # require_staff acepta al operador (rol user)
        assert require_staff(operator) is operator
        # require_admin lo rechaza (la gestión de cuentas sigue admin-only)
        with pytest.raises(HTTPException) as exc:
            require_admin(operator)
        assert exc.value.status_code == 403
    finally:
        db.close()
