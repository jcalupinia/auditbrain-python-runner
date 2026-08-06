"""Historial de homologaciones por cliente.

Es la memoria del motor: lo que el auditor confirmó una vez no se vuelve a
preguntar. La clave es el cliente, no el proyecto, para que lo aprendido en
el ejercicio 2025 sirva en el 2026.
"""

from __future__ import annotations

import datetime
import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.aud.obligaciones_fiscales.mayor.models import MayorHomologacion


def _norm(texto: str) -> str:
    s = unicodedata.normalize("NFKD", texto or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.lower().split())


def historial_de_cliente(db: Session, *, client_id: int) -> dict[str, str]:
    """{codigo_cuenta: categoria} — el formato que espera `clasificar()`."""
    filas = db.execute(
        select(MayorHomologacion).where(MayorHomologacion.client_id == client_id)
    ).scalars()
    return {f.codigo_cuenta: f.categoria for f in filas}


def guardar_homologaciones(
    db: Session,
    *,
    client_id: int,
    asignaciones: list[dict],
    user_id: int | None = None,
) -> int:
    """Upsert de las cuentas que el auditor aprobó. Devuelve cuántas guardó."""
    ahora = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    guardadas = 0
    for a in asignaciones:
        categoria = a.get("categoria")
        codigo = (a.get("codigo_cuenta") or "").strip()
        if not categoria or not codigo:
            continue
        fila = db.execute(
            select(MayorHomologacion).where(
                MayorHomologacion.client_id == client_id,
                MayorHomologacion.codigo_cuenta == codigo,
            )
        ).scalar_one_or_none()
        if fila is None:
            db.add(
                MayorHomologacion(
                    client_id=client_id,
                    codigo_cuenta=codigo,
                    nombre_norm=_norm(a.get("nombre_cuenta", "")),
                    categoria=categoria,
                    tarifa=a.get("tarifa"),
                    veces_usada=1,
                    creada_por_user_id=user_id,
                    created_at=ahora,
                    updated_at=ahora,
                )
            )
        else:
            fila.categoria = categoria
            fila.tarifa = a.get("tarifa")
            fila.nombre_norm = _norm(a.get("nombre_cuenta", "")) or fila.nombre_norm
            fila.veces_usada += 1
            fila.updated_at = ahora
            db.add(fila)
        guardadas += 1
    if guardadas:
        db.commit()
    return guardadas
