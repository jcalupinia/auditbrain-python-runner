"""Prueba aislada de permisos del endpoint de saldos (sin PostgreSQL)."""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.app.api.mayor_persistido import verificar_acceso
from backend.app.auth.models import Role


class DB:
    def __init__(self, project, member=True):
        self.project = project
        self.member = member
    def get(self, cls, project_id):
        return self.project if self.project.id == project_id else None
    def query(self, *args):
        return self
    def filter(self, *args):
        return self
    def first(self):
        return (1,) if self.member else None


def test_admin_organizacion_correcta():
    p = SimpleNamespace(id=10, organization_id=7, is_active=True)
    u = SimpleNamespace(id=1, organization_id=7, role=Role.admin, is_active=True)
    assert verificar_acceso(DB(p), u, 10) is p


def test_aislamiento_organizacion():
    p = SimpleNamespace(id=10, organization_id=7, is_active=True)
    u = SimpleNamespace(id=1, organization_id=8, role=Role.admin, is_active=True)
    with pytest.raises(HTTPException) as err:
        verificar_acceso(DB(p), u, 10)
    assert err.value.status_code == 404


def test_operador_sin_membresia():
    p = SimpleNamespace(id=10, organization_id=7, is_active=True)
    u = SimpleNamespace(id=2, organization_id=7, role=Role.user, is_active=True)
    with pytest.raises(HTTPException) as err:
        verificar_acceso(DB(p, member=False), u, 10)
    assert err.value.status_code == 404


def test_cliente_no_accede():
    p = SimpleNamespace(id=10, organization_id=7, is_active=True)
    u = SimpleNamespace(id=3, organization_id=7, role=Role.client, is_active=True)
    with pytest.raises(HTTPException) as err:
        verificar_acceso(DB(p), u, 10)
    assert err.value.status_code == 403
