"""Fail-closed tenant resolution for AuditSmart cost files and jobs.

The caller supplies a *server-authenticated* user and a project ID. Never
accept client_id/organization_id from HTTP request bodies or query parameters.
"""
from __future__ import annotations
from sqlalchemy.orm import Session
from backend.app.client_portal.costos.ingestion import Tenant
from backend.app.client_portal.entitlements import can_access_tool, is_operator
from backend.app.context.models import Client, Project

TOOL_CODE = "SOFTWARE_COSTOS"

def has_entitlement(db: Session, user) -> bool:
    return is_operator(user) or can_access_tool(db, user.id, TOOL_CODE)

def resolve_tenant(db: Session, user, project_id: int) -> Tenant:
    """Resolve explicit client-scoped ownership before any import or read."""
    if not getattr(user, "is_active", False) or not has_entitlement(db, user):
        raise PermissionError("cost tool not available")
    org_id = getattr(user, "organization_id", None)
    client_id = getattr(user, "client_id", None)
    if type(org_id) is not int or org_id <= 0 or type(client_id) is not int or client_id <= 0:
        raise PermissionError("explicit organization/client scope required")
    if type(project_id) is not int or project_id <= 0:
        raise PermissionError("invalid project scope")
    project = db.get(Project, project_id)
    client = db.get(Client, client_id)
    if not project or not client or not getattr(project, "is_active", False) or not getattr(client, "is_active", False):
        raise PermissionError("project or client unavailable")
    if (
        project.organization_id != org_id
        or project.client_id != client_id
        or client.organization_id != org_id
    ):
        raise PermissionError("project not in user's tenant")
    return Tenant(organization_id=org_id, client_id=client_id, project_id=project_id)
