"""Consulta de saldos del mayor persistido. Solo operadores autorizados.

Este router es opt-in: requiere registro explícito en la app y tablas
mayor_ingesta_* instaladas mediante migración revisada.
"""
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.auth.deps import get_current_user
from backend.app.auth.models import Role, User
from backend.app.context.models import Project, ProjectMember
from backend.app.db.session import get_db

router = APIRouter(prefix="/ingesta/mayores", tags=["ingesta-mayores"])


def verificar_acceso(db: Session, user: User, project_id: int) -> Project:
    if not user.is_active or user.role not in (Role.admin, Role.user):
        raise HTTPException(status_code=403, detail="Acceso restringido a operadores")
    project = db.get(Project, project_id)
    if not project or not project.is_active or user.organization_id != project.organization_id:
        raise HTTPException(status_code=404, detail="Expediente no disponible")
    # El admin solo tiene acceso a proyectos de su organización.
    if user.role != Role.admin:
        member = db.query(ProjectMember.id).filter(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user.id,
        ).first()
        if not member:
            raise HTTPException(status_code=404, detail="Expediente no disponible")
    return project


@router.get("/{project_id}/cuentas/{codigo}/saldo")
def saldo_cuenta(
    project_id: int,
    codigo: str,
    periodo: str = Query(min_length=4, max_length=64),
    fecha_corte: date = Query(...),
    lote_id: int = Query(..., gt=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = verificar_acceso(db, user, project_id)
    # El lote explícito evita sumar distintas versiones del mismo mayor.
    sql = text("""
        SELECT COUNT(*) AS movimientos,
               COALESCE(SUM(m.debe),0) AS debe,
               COALESCE(SUM(m.haber),0) AS haber
        FROM mayor_ingesta_movimientos m
        JOIN mayor_ingesta_lotes l ON l.id=m.lote_id
        WHERE l.id=:lote_id AND l.organization_id=:org
          AND l.project_id=:project AND l.periodo=:periodo
          AND m.codigo=:codigo AND m.fecha<=:fecha
    """)
    try:
        # La existencia del lote se valida independientemente para no
        # confundir un saldo cero con un lote ajeno o inexistente.
        lote = db.execute(text("""
            SELECT id FROM mayor_ingesta_lotes
            WHERE id=:lote_id AND organization_id=:org
              AND project_id=:project AND periodo=:periodo
        """), {"lote_id": lote_id, "org": str(project.organization_id),
               "project": str(project.id), "periodo": periodo}).first()
        if lote is None:
            raise HTTPException(status_code=404, detail="Lote no disponible")
        row = db.execute(sql, {
            "lote_id": lote_id, "org": str(project.organization_id),
            "project": str(project.id), "periodo": periodo,
            "codigo": codigo, "fecha": fecha_corte,
        }).one()
    except HTTPException:
        raise
    except Exception:
        # Nunca revelar detalles SQL ni credenciales en errores HTTP.
        raise HTTPException(status_code=503, detail="Consulta no disponible")
    debe, haber = Decimal(row.debe), Decimal(row.haber)
    return {
        "organization_id": project.organization_id,
        "project_id": project.id,
        "periodo": periodo,
        "lote_id": lote_id,
        "codigo": codigo,
        "fecha_corte": fecha_corte.isoformat(),
        "movimientos": row.movimientos,
        "debe": str(debe),
        "haber": str(haber),
        "saldo": str(debe - haber),
    }
