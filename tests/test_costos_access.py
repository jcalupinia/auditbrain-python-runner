"""Access boundary for AuditSmart; all callers must derive tenant from server-side User."""
from types import SimpleNamespace
import pytest
from backend.app.client_portal.costos import access

class FakeDB:
    def __init__(self, project, client):
        self.project, self.client = project, client
    def get(self, cls, key):
        if cls.__name__ == "Project": return self.project if self.project and self.project.id == key else None
        if cls.__name__ == "Client": return self.client if self.client and self.client.id == key else None
        return None

def fixture_data():
    user = SimpleNamespace(id=22, organization_id=1, client_id=10, role=SimpleNamespace(value="client"), is_active=True)
    project = SimpleNamespace(id=100, organization_id=1, client_id=10, is_active=True)
    client = SimpleNamespace(id=10, organization_id=1, is_active=True)
    return user, project, client

def test_valid_tenant(monkeypatch):
    monkeypatch.setattr(access, "has_entitlement", lambda db, user: True)
    u,p,c=fixture_data()
    t=access.resolve_tenant(FakeDB(p,c),u,100)
    assert (t.organization_id,t.client_id,t.project_id)==(1,10,100)

@pytest.mark.parametrize("alter", ["other_client","other_org","inactive_client","inactive_project","missing_project","missing_org","missing_client"])
def test_denies_invalid_scope(monkeypatch, alter):
    monkeypatch.setattr(access,"has_entitlement",lambda db,u:True)
    u,p,c=fixture_data()
    if alter=="other_client": p.client_id=11
    if alter=="other_org": p.organization_id=2
    if alter=="inactive_client": c.is_active=False
    if alter=="inactive_project": p.is_active=False
    if alter=="missing_project": p=None
    if alter=="missing_org": u.organization_id=None
    if alter=="missing_client": u.client_id=None
    with pytest.raises(PermissionError):
        access.resolve_tenant(FakeDB(p,c),u,100)

def test_denies_without_commercial_entitlement(monkeypatch):
    monkeypatch.setattr(access, "has_entitlement",lambda db,u:False)
    u,p,c=fixture_data()
    with pytest.raises(PermissionError): access.resolve_tenant(FakeDB(p,c),u,100)

def test_denies_staff_without_explicit_project_scope(monkeypatch):
    monkeypatch.setattr(access, "has_entitlement",lambda db,u:True)
    u,p,c=fixture_data()
    u.role=SimpleNamespace(value="admin")
    u.client_id=None
    with pytest.raises(PermissionError): access.resolve_tenant(FakeDB(p,c),u,100)
