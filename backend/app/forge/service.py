"""Lógica del módulo Forge: persistencia del cerebro y compilación vía el motor.

El motor (``engine/``) es puro y determinista; aquí solo se construye el objeto
``Brain`` a partir de las filas de la BD y se delega en el adaptador.
"""

from __future__ import annotations

import re
import unicodedata

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

_VALID_MEMORY_TYPES = ("user", "feedback", "project", "reference")


def _slugify(name: str) -> str:
    ascii_name = (
        unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    )
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-") or "memoria"

from .engine.adapters import get_adapter
from .engine.model import (
    Agent,
    Brain,
    BrainMeta,
    Capability,
    Connector,
    MemoryEntry,
    Persona,
    Rule,
    Skill,
)
from .models import ForgeBrain
from .schemas import BrainCreate, BrainOut


def list_brains(db: Session, user_id: int) -> list[ForgeBrain]:
    stmt = (
        select(ForgeBrain)
        .where(ForgeBrain.owner_user_id == user_id)
        .order_by(ForgeBrain.id)
    )
    return list(db.execute(stmt).scalars().all())


def get_owned_brain(db: Session, user_id: int, brain_id: int) -> ForgeBrain:
    row = db.get(ForgeBrain, brain_id)
    if row is None or row.owner_user_id != user_id:
        raise HTTPException(status_code=404, detail="Cerebro no encontrado")
    return row


def create_brain(db: Session, user, payload: BrainCreate) -> ForgeBrain:
    row = ForgeBrain(
        organization_id=getattr(user, "organization_id", None),
        owner_user_id=user.id,
        slug=payload.slug,
        name=payload.name,
        organization=payload.organization,
        language=payload.language,
        version=payload.version,
        targets=payload.targets,
        rules=payload.rules,
        memory=payload.memory,
        skills=payload.skills,
        agents=payload.agents,
        personas=payload.personas,
        connectors=payload.connectors,
        capabilities=payload.capabilities,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def to_out(row: ForgeBrain) -> BrainOut:
    return BrainOut(
        id=row.id,
        name=row.name,
        slug=row.slug,
        organization=row.organization,
        language=row.language,
        version=row.version,
        targets=list(row.targets or []),
    )


def build_brain(row: ForgeBrain) -> Brain:
    """Construye el objeto Brain del motor a partir de la fila de BD.

    Puede lanzar ``pydantic.ValidationError`` (subclase de ``ValueError``) si
    alguna colección almacenada no cumple el esquema.
    """
    return Brain(
        meta=BrainMeta(
            name=row.name,
            slug=row.slug,
            organization=row.organization,
            language=row.language,
            version=row.version,
            targets=list(row.targets or ["claude-code"]),
        ),
        rules=[Rule(**r) for r in row.rules],
        memory=[MemoryEntry(**m) for m in row.memory],
        skills=[Skill(**s) for s in row.skills],
        agents=[Agent(**a) for a in row.agents],
        personas=[Persona(**p) for p in row.personas],
        connectors=[Connector(**c) for c in row.connectors],
        capabilities=[Capability(**c) for c in row.capabilities],
    )


def compile_brain(row: ForgeBrain, target: str) -> dict[str, str]:
    """Compila el cerebro al ``target``. Lanza KeyError si el destino no existe."""
    brain = build_brain(row)
    return get_adapter(target).compile(brain)


def list_memory(row: ForgeBrain) -> list[dict]:
    return list(row.memory or [])


def add_memory(
    db: Session,
    row: ForgeBrain,
    name: str,
    description: str,
    body: str = "",
    type: str = "project",
) -> dict:
    """Añade (o reemplaza por slug) una entrada de memoria del cerebro y persiste."""
    if type not in _VALID_MEMORY_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"type debe ser uno de {_VALID_MEMORY_TYPES}",
        )
    slug = _slugify(name)
    entry = {
        "slug": slug,
        "name": name,
        "description": description,
        "type": type,
        "body": body,
    }
    # Reasignar la lista para que SQLAlchemy detecte el cambio del JSON.
    row.memory = [m for m in (row.memory or []) if m.get("slug") != slug] + [entry]
    db.commit()
    db.refresh(row)
    return entry
