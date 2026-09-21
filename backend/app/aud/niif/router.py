"""Endpoints HTTP de las fichas de diseño NIIF (AUD, staff).

Permisos: ``require_staff`` — admin y operadores (rol ``user``), igual que el
Motor de balances. Es la política vigente de la firma: el operador hace lo
mismo que el admin salvo gestión de cuentas. Además, el circuito pedido por
el dueño necesita que un auditor distinto del autor pueda marcar la ficha
como probada; restringir a admin lo haría imposible en la práctica.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.aud.niif import service
from backend.app.aud.niif.models import NiifFicha
from backend.app.aud.niif.schemas import (
    ESTADO_EN_DISENO,
    ESTADOS_VALIDOS,
    EstadoIn,
    FichaIn,
    FichaOut,
)
from backend.app.auth.deps import require_staff
from backend.app.auth.models import User
from backend.app.db.session import get_db

router = APIRouter(prefix="/aud/niif", tags=["aud-niif"])


def _get_ficha(db: Session, ficha_id: int) -> NiifFicha:
    ficha = db.get(NiifFicha, ficha_id)
    if ficha is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Ficha no encontrada.")
    return ficha


@router.post("/fichas", response_model=FichaOut, status_code=status.HTTP_201_CREATED)
def crear_ficha(
    body: FichaIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
) -> NiifFicha:
    ficha = NiifFicha(
        nombre=body.nombre,
        rubro=body.rubro,
        norma=body.norma,
        parrafo=body.parrafo,
        items=[i.model_dump() for i in body.items],
        salidas=[s.model_dump() for s in body.salidas],
        estado=ESTADO_EN_DISENO,
        autor_user_id=user.id,
        autor_email=user.email,
    )
    db.add(ficha)
    db.commit()
    db.refresh(ficha)
    return ficha


@router.get("/fichas", response_model=list[FichaOut])
def listar_fichas(
    db: Session = Depends(get_db),
    _user: User = Depends(require_staff),
) -> list[NiifFicha]:
    """Todas las fichas de la firma, la más recientemente tocada primero.

    No se filtra por autor a propósito: el revisor tiene que ver la ficha
    que diseñó otro; ese es el motivo de que esto viva en la base y no en
    el navegador.
    """
    stmt = select(NiifFicha).order_by(NiifFicha.updated_at.desc(), NiifFicha.id.desc())
    return list(db.scalars(stmt))


@router.get("/fichas/{ficha_id}", response_model=FichaOut)
def leer_ficha(
    ficha_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_staff),
) -> NiifFicha:
    return _get_ficha(db, ficha_id)


@router.patch("/fichas/{ficha_id}", response_model=FichaOut)
def actualizar_ficha(
    ficha_id: int,
    body: FichaIn,
    db: Session = Depends(get_db),
    _user: User = Depends(require_staff),
) -> NiifFicha:
    """Reemplaza el contenido de la ficha. Solo mientras está en diseño:
    una ficha ya probada no puede cambiar bajo los pies del revisor."""
    ficha = _get_ficha(db, ficha_id)
    if ficha.estado != ESTADO_EN_DISENO:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"La ficha está en estado «{ficha.estado}» y ya no se edita.",
        )
    ficha.nombre = body.nombre
    ficha.rubro = body.rubro
    ficha.norma = body.norma
    ficha.parrafo = body.parrafo
    ficha.items = [i.model_dump() for i in body.items]
    ficha.salidas = [s.model_dump() for s in body.salidas]
    db.commit()
    db.refresh(ficha)
    return ficha


@router.post("/fichas/{ficha_id}/estado", response_model=FichaOut)
def cambiar_estado(
    ficha_id: int,
    body: EstadoIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
) -> NiifFicha:
    """Avanza la ficha en el circuito. Nunca salta un estado."""
    if body.estado not in ESTADOS_VALIDOS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Estado desconocido: {body.estado}.",
        )
    ficha = _get_ficha(db, ficha_id)
    try:
        service.aplicar_transicion(ficha, body.estado, user)
    except service.TransicionInvalida as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc))
    db.commit()
    db.refresh(ficha)
    return ficha


@router.delete("/fichas/{ficha_id}", status_code=status.HTTP_200_OK)
def eliminar_ficha(
    ficha_id: int,
    confirmar_nombre: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
) -> dict:
    """Elimina una ficha de diseño. Hay que escribir su nombre para confirmar.

    Mismos resguardos que el borrado de herramientas y de encargos en el sitio:
    la confirmación es explícita y quién borró queda en la respuesta. Las fichas
    descartadas no se acumulan para siempre en la lista de la firma.
    """
    ficha = _get_ficha(db, ficha_id)
    if confirmar_nombre != ficha.nombre:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Escriba el nombre de la ficha para confirmar la eliminación.",
        )
    nombre, estado = ficha.nombre, ficha.estado
    db.delete(ficha)
    db.commit()
    return {
        "eliminada": True,
        "id": ficha_id,
        "nombre": nombre,
        "estado_al_eliminar": estado,
        "eliminada_por": user.email,
    }
