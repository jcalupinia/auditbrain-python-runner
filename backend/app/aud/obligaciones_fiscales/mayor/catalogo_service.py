"""Catálogo de categorías en base de datos.

La semilla sale de `catalogo.CATEGORIAS` (la fuente en memoria que usa el
motor). Una organización puede añadir categorías propias sin tocar código.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.aud.obligaciones_fiscales.mayor.catalogo import CATEGORIAS
from backend.app.aud.obligaciones_fiscales.mayor.models import MayorCategoria


def sembrar_categorias_de_sistema(db: Session) -> int:
    """Crea las categorías de sistema que falten. Idempotente."""
    existentes = {
        c.codigo
        for c in db.execute(
            select(MayorCategoria).where(MayorCategoria.es_sistema.is_(True))
        ).scalars()
    }
    creadas = 0
    for cat in CATEGORIAS.values():
        if cat.codigo in existentes:
            continue
        db.add(
            MayorCategoria(
                organization_id=None,
                codigo=cat.codigo,
                nombre=cat.nombre,
                naturaleza_esperada=cat.naturaleza_esperada,
                orden=cat.orden,
                es_sistema=True,
            )
        )
        creadas += 1
    if creadas:
        db.commit()
    return creadas


def categorias_visibles(db: Session, *, organization_id: int | None) -> list[MayorCategoria]:
    """Categorías de sistema + las propias de la organización, activas."""
    sembrar_categorias_de_sistema(db)
    stmt = (
        select(MayorCategoria)
        .where(
            MayorCategoria.activa.is_(True),
            (MayorCategoria.organization_id.is_(None))
            | (MayorCategoria.organization_id == organization_id),
        )
        .order_by(MayorCategoria.orden, MayorCategoria.codigo)
    )
    return list(db.execute(stmt).scalars())
