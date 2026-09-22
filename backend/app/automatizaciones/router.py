"""Endpoints /api/v1/staff/automatizaciones/* — Tarea 6 del plan.

Capa fina sobre ``service.py``: valida el payload, traduce
``AutomatizacionError`` a 400/409 y ``SupabaseAdminError`` a 502 con un
mensaje genérico (el detalle real solo va al log, nunca al cliente).
"""

from __future__ import annotations

import logging
from contextlib import contextmanager

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.auth.deps import require_admin, require_staff
from backend.app.auth.models import User
from backend.app.automatizaciones import schemas, service
from backend.app.automatizaciones.models import AutCuenta
from backend.app.automatizaciones.supabase_admin import SupabaseAdminError
from backend.app.context.models import Client
from backend.app.db.session import get_db

router = APIRouter(prefix="/staff/automatizaciones", tags=["automatizaciones"])
log = logging.getLogger(__name__)

MSG_502 = "No se pudo contactar al servidor de Presupuestos IA."


@contextmanager
def _mapear_errores(accion: str, actor: str, cuenta_id: int | str):
    """Traduce los errores de negocio/infra al HTTP correspondiente.

    ``SupabaseAdminError`` nunca se expone tal cual: el detalle (que puede
    traer fragmentos de la respuesta del servidor remoto) solo va al log.
    """
    try:
        yield
    except SupabaseAdminError as e:
        log.error("aut %s: fallo Supabase actor=%s cuenta=%s: %s", accion, actor, cuenta_id, e)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=MSG_502) from None
    except service.AutomatizacionError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e)) from None


def _con_nombres(db: Session, filas: list[dict]) -> list[dict]:
    ids = {f["client_id"] for f in filas}
    nombres = (
        {c.id: c.name for c in db.query(Client).filter(Client.id.in_(ids)).all()} if ids else {}
    )
    for f in filas:
        f["client_nombre"] = nombres.get(f["client_id"], "")
    return filas


def _una(db: Session, cuenta: AutCuenta) -> dict:
    """Serializa una sola cuenta reusando ``service.listar`` (misma lógica
    de estado efectivo/etiqueta/vigencia que el listado, sin duplicarla)."""
    filas = service.listar(db, client_id=cuenta.client_id)
    fila = next(f for f in filas if f["id"] == cuenta.id)
    return _con_nombres(db, [fila])[0]


def _obtener_o_400(db: Session, cuenta_id: int) -> AutCuenta:
    cuenta = db.get(AutCuenta, cuenta_id)
    if cuenta is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail=f"La cuenta {cuenta_id} no existe."
        )
    return cuenta


@router.get(
    "/cuentas",
    response_model=list[schemas.CuentaOut],
    dependencies=[Depends(require_staff)],
)
def listar_cuentas_endpoint(client_id: int | None = None, db: Session = Depends(get_db)):
    return _con_nombres(db, service.listar(db, client_id=client_id))


@router.post("/cuentas", response_model=schemas.CuentaOut, status_code=status.HTTP_201_CREATED)
def crear_cuenta_endpoint(
    payload: schemas.CuentaCreate,
    operador: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    ya = (
        db.query(AutCuenta)
        .filter_by(client_id=payload.client_id, herramienta=payload.herramienta)
        .first()
    )
    if ya is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=(
                f"El cliente {payload.client_id} ya tiene una cuenta de "
                f"{payload.herramienta}."
            ),
        )
    with _mapear_errores("alta", operador.email, payload.client_id):
        cuenta = service.crear(
            db,
            client_id=payload.client_id,
            herramienta=payload.herramienta,
            empresa_nombre=payload.empresa_nombre,
            admin_email=payload.admin_email,
            admin_nombre=payload.admin_nombre,
            creado_por=operador.email,
            vigencia_hasta=payload.vigencia_hasta,
        )
    return _una(db, cuenta)


@router.post("/cuentas/{cuenta_id}/reenviar-acceso", response_model=schemas.CuentaOut)
def reenviar_acceso_endpoint(
    cuenta_id: int, operador: User = Depends(require_staff), db: Session = Depends(get_db)
):
    with _mapear_errores("reenvio", operador.email, cuenta_id):
        cuenta = service.reenviar_acceso(db, cuenta_id, actor=operador.email)
    return _una(db, cuenta)


@router.post("/cuentas/{cuenta_id}/suspender", response_model=schemas.CuentaOut)
def suspender_endpoint(
    cuenta_id: int, operador: User = Depends(require_staff), db: Session = Depends(get_db)
):
    with _mapear_errores("suspension", operador.email, cuenta_id):
        cuenta = service.suspender(db, cuenta_id, actor=operador.email)
    return _una(db, cuenta)


@router.post("/cuentas/{cuenta_id}/reactivar", response_model=schemas.CuentaOut)
def reactivar_endpoint(
    cuenta_id: int, operador: User = Depends(require_staff), db: Session = Depends(get_db)
):
    with _mapear_errores("reactivacion", operador.email, cuenta_id):
        cuenta = service.reactivar(db, cuenta_id, actor=operador.email)
    return _una(db, cuenta)


@router.post("/cuentas/{cuenta_id}/refrescar-empresa", response_model=schemas.CuentaOut)
def refrescar_empresa_endpoint(
    cuenta_id: int, operador: User = Depends(require_staff), db: Session = Depends(get_db)
):
    cuenta = _obtener_o_400(db, cuenta_id)
    # service.refrescar_empresa ya atrapa SupabaseAdminError internamente
    # (mejor esfuerzo: si la app no responde, devuelve None sin romper).
    service.refrescar_empresa(db, cuenta)
    log.info("aut refrescar_empresa: actor=%s cuenta=%s", operador.email, cuenta_id)
    return _una(db, cuenta)


@router.delete("/cuentas/{cuenta_id}")
def borrar_cuenta_endpoint(
    cuenta_id: int,
    confirmado: bool = Query(False),
    operador: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    with _mapear_errores("borrado", operador.email, cuenta_id):
        service.borrar(db, cuenta_id, actor=operador.email, confirmado=confirmado)
    return {"ok": True}
