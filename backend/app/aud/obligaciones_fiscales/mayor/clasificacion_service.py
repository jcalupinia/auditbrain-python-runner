"""Clasificación de un job: se guarda, se muestra al auditor, se corrige."""

from __future__ import annotations

import datetime
from dataclasses import asdict

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.app.aud.obligaciones_fiscales.mayor.models import MayorClasificacionJob
from backend.app.aud.obligaciones_fiscales.mayor.tipos import (
    PerfilCuenta,
    ResultadoClasificacion,
)


def guardar_clasificacion(
    db: Session,
    *,
    job_id: int,
    resultados: list[ResultadoClasificacion],
    perfiles: dict[str, PerfilCuenta],
) -> int:
    """Reemplaza la clasificación del job por la recién calculada."""
    db.execute(delete(MayorClasificacionJob).where(MayorClasificacionJob.job_id == job_id))
    for r in resultados:
        p = perfiles.get(r.codigo)
        db.add(
            MayorClasificacionJob(
                job_id=job_id,
                codigo_cuenta=r.codigo,
                nombre_cuenta=r.nombre,
                n_movimientos=p.n_movimientos if p else 0,
                debe=p.debe if p else 0.0,
                haber=p.haber if p else 0.0,
                por_mes_json=dict(p.por_mes) if p else None,
                categoria_sugerida=r.categoria,
                categoria_final=r.categoria,
                tarifa=r.tarifa,
                confianza=r.confianza,
                origen=r.origen,
                senales_json=[asdict(s) for s in r.senales],
            )
        )
    db.commit()
    return len(resultados)


def clasificacion_de_job(db: Session, *, job_id: int) -> list[MayorClasificacionJob]:
    stmt = (
        select(MayorClasificacionJob)
        .where(MayorClasificacionJob.job_id == job_id)
        .order_by(MayorClasificacionJob.codigo_cuenta)
    )
    return list(db.execute(stmt).scalars())


def aplicar_correcciones(
    db: Session,
    *,
    job_id: int,
    correcciones: list[dict],
    user_id: int | None = None,
) -> int:
    """Aplica lo que decidió el auditor. Devuelve cuántas filas tocó."""
    ahora = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    por_codigo = {f.codigo_cuenta: f for f in clasificacion_de_job(db, job_id=job_id)}
    tocadas = 0
    for c in correcciones:
        fila = por_codigo.get((c.get("codigo_cuenta") or "").strip())
        if fila is None:
            continue
        nueva = c.get("categoria")
        if nueva != fila.categoria_final:
            fila.categoria_final = nueva
            fila.corregida = True
            fila.origen = "manual"
        fila.aprobada_por_user_id = user_id
        fila.aprobada_at = ahora
        db.add(fila)
        tocadas += 1
    if tocadas:
        db.commit()
    return tocadas
