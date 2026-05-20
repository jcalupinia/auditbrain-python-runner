"""Servicios del contexto operativo: orgs, clientes, proyectos, contexto del usuario."""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.auth.models import User
from backend.app.context.models import Client, Organization, Project, ProjectMember


# ---------------------------------------------------------------------------
# Organization
# ---------------------------------------------------------------------------

DEFAULT_ORG_NAME = "AuditBrain"
DEFAULT_ORG_SLUG = "auditbrain"


def _slugify(value: str, fallback: str = "org") -> str:
    s = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return s or fallback


def get_organization_by_slug(db: Session, slug: str) -> Organization | None:
    return db.execute(
        select(Organization).where(Organization.slug == slug)
    ).scalar_one_or_none()


def get_or_create_default_organization(db: Session) -> Organization:
    """Devuelve la organización por defecto (la crea si no existe).

    Permite que el comportamiento single-tenant siga funcionando sin
    configuración: el primer usuario y los existentes se enganchan aquí.
    """
    org = get_organization_by_slug(db, DEFAULT_ORG_SLUG)
    if org:
        return org
    org = Organization(name=DEFAULT_ORG_NAME, slug=DEFAULT_ORG_SLUG)
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def ensure_user_has_organization(db: Session, user: User) -> User:
    if user.organization_id:
        return user
    org = get_or_create_default_organization(db)
    user.organization_id = org.id
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def assign_legacy_users_to_default_org(db: Session) -> int:
    """Bootstrap: asigna la org por defecto a cualquier usuario sin tenant.

    Idempotente. Retorna cuántos se migraron.
    """
    org = get_or_create_default_organization(db)
    legacy = db.execute(
        select(User).where(User.organization_id.is_(None))
    ).scalars().all()
    n = 0
    for u in legacy:
        u.organization_id = org.id
        db.add(u)
        n += 1
    if n:
        db.commit()
    return n


# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------

def list_clients(db: Session, organization_id: int) -> list[Client]:
    return list(
        db.execute(
            select(Client)
            .where(Client.organization_id == organization_id)
            .order_by(Client.name)
        ).scalars()
    )


def get_client(db: Session, client_id: int, organization_id: int) -> Client | None:
    return db.execute(
        select(Client).where(
            Client.id == client_id, Client.organization_id == organization_id
        )
    ).scalar_one_or_none()


def create_client(
    db: Session,
    organization_id: int,
    name: str,
    tax_id: str | None = None,
    sector: str | None = None,
) -> Client:
    client = Client(
        organization_id=organization_id,
        name=name.strip(),
        tax_id=tax_id,
        sector=sector,
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

def list_user_projects(db: Session, user: User) -> list[Project]:
    """Proyectos visibles para el usuario.

    - admin: todos los proyectos de su organización.
    - user: solo aquellos donde es ProjectMember (en la misma org).
    """
    if not user.organization_id:
        return []
    if user.role.value == "admin":
        return list(
            db.execute(
                select(Project)
                .where(Project.organization_id == user.organization_id)
                .order_by(Project.created_at.desc())
            ).scalars()
        )
    return list(
        db.execute(
            select(Project)
            .join(ProjectMember, ProjectMember.project_id == Project.id)
            .where(
                Project.organization_id == user.organization_id,
                ProjectMember.user_id == user.id,
            )
            .order_by(Project.created_at.desc())
        ).scalars()
    )


def get_project(
    db: Session, project_id: int, organization_id: int
) -> Project | None:
    return db.execute(
        select(Project).where(
            Project.id == project_id, Project.organization_id == organization_id
        )
    ).scalar_one_or_none()


def user_can_access_project(db: Session, user: User, project: Project) -> bool:
    if not user.organization_id or project.organization_id != user.organization_id:
        return False
    if user.role.value == "admin":
        return True
    membership = db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project.id,
            ProjectMember.user_id == user.id,
        )
    ).scalar_one_or_none()
    return membership is not None


def create_project(
    db: Session,
    organization_id: int,
    client_id: int,
    name: str,
    module_code: str | None = None,
    period_label: str | None = None,
    period_start=None,
    period_end=None,
) -> Project:
    proj = Project(
        organization_id=organization_id,
        client_id=client_id,
        name=name.strip(),
        module_code=(module_code or "").strip().upper() or None,
        period_label=period_label,
        period_start=period_start,
        period_end=period_end,
    )
    db.add(proj)
    db.commit()
    db.refresh(proj)
    return proj


def add_project_member(
    db: Session, project_id: int, user_id: int, project_role: str = "member"
) -> ProjectMember:
    existing = db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    ).scalar_one_or_none()
    if existing:
        existing.project_role = project_role
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing
    pm = ProjectMember(
        project_id=project_id, user_id=user_id, project_role=project_role
    )
    db.add(pm)
    db.commit()
    db.refresh(pm)
    return pm


# ---------------------------------------------------------------------------
# Contexto del usuario
# ---------------------------------------------------------------------------

def get_user_context(db: Session, user: User) -> dict:
    """Estado completo de contexto del usuario (org + proyectos + activo)."""
    user = ensure_user_has_organization(db, user)
    org = db.get(Organization, user.organization_id) if user.organization_id else None
    projects = list_user_projects(db, user)
    active_project = None
    active_client = None
    if user.active_project_id:
        active_project = db.get(Project, user.active_project_id)
        if active_project and not user_can_access_project(db, user, active_project):
            # El proyecto activo ya no es visible: lo desclavamos.
            user.active_project_id = None
            db.add(user)
            db.commit()
            active_project = None
    if active_project:
        active_client = db.get(Client, active_project.client_id)
    return {
        "organization": org,
        "active_project": active_project,
        "active_client": active_client,
        "projects": projects,
    }


def set_active_project(db: Session, user: User, project_id: int | None) -> User:
    if project_id is None:
        user.active_project_id = None
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    proj = db.get(Project, project_id)
    if not proj or not user_can_access_project(db, user, proj):
        raise PermissionError("El proyecto no existe o no es accesible para el usuario.")
    user.active_project_id = proj.id
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
