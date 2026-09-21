"""Rutas HTTP del ciclo real de una prueba (E6).

Permisos: ``require_staff`` (admin y operadores), por decisión del dueño del
2026-09-21; además, el usuario tiene que poder acceder al proyecto, con la misma
regla que el resto del portal (``user_can_access_project``).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.aud.niif.ciclo import servicio
from backend.app.aud.niif.ciclo.models import Prueba
from backend.app.aud.niif.ciclo.reglas import ReglaIncumplida
from backend.app.aud.niif.models import NiifFicha
from backend.app.auth.deps import require_staff
from backend.app.auth.models import User
from backend.app.context.service import get_project, user_can_access_project
from backend.app.db.session import get_db

router = APIRouter(prefix="/aud/ciclo", tags=["aud-ciclo"])


class NuevaPruebaIn(BaseModel):
    origen: str = Field(min_length=1, max_length=40)
    tributario: bool = False


class AccionIn(BaseModel):
    accion: str = Field(min_length=1, max_length=40)
    revision: int
    datos: dict = Field(default_factory=dict)


class DefinicionIn(BaseModel):
    definicion: dict
    filas: list[dict]


def _proyecto(db: Session, user: User, project_id: int):
    p = get_project(db, project_id, user.organization_id) if user.organization_id else None
    if p is None or not user_can_access_project(db, user, p):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Proyecto no encontrado.")
    if (p.module_code or "").upper() != "AUD":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Las pruebas NIIF se aplican a proyectos del módulo AUD.")
    return p


def _prueba(db: Session, user: User, prueba_id: int) -> Prueba:
    p = db.get(Prueba, prueba_id)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Prueba no encontrada.")
    _proyecto(db, user, p.project_id)
    return p


def _salida(p: Prueba) -> dict:
    return {
        "id": p.id, "project_id": p.project_id, "version": p.version, "estado": p.estado,
        "origen": p.origen, "definicion": p.definicion, "registro": p.registro,
        "revision": p.revision, "creada_por": p.creada_por,
        "creada_en": p.creada_en.isoformat() if p.creada_en else None,
        "actualizada_en": p.actualizada_en.isoformat() if p.actualizada_en else None,
    }


def _regla(fn):
    try:
        return fn()
    except ReglaIncumplida as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))
    except servicio.Conflicto as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(e))


@router.get("/proyectos/{project_id}/ficha")
def leer_ficha(project_id: int, db: Session = Depends(get_db), user: User = Depends(require_staff)) -> dict:
    _proyecto(db, user, project_id)
    return {"ficha": servicio.leer_ficha(db, project_id)}


@router.put("/proyectos/{project_id}/ficha")
def guardar_ficha(project_id: int, body: dict, db: Session = Depends(get_db), user: User = Depends(require_staff)) -> dict:
    _proyecto(db, user, project_id)
    return {"ficha": _regla(lambda: servicio.guardar_ficha(db, project_id, body, user.email))}


@router.get("/herramientas")
def herramientas(db: Session = Depends(get_db), user: User = Depends(require_staff)) -> list[dict]:
    return servicio.herramientas_disponibles(db)


@router.get("/proyectos/{project_id}/pruebas")
def listar(project_id: int, db: Session = Depends(get_db), user: User = Depends(require_staff)) -> list[dict]:
    _proyecto(db, user, project_id)
    filas = db.execute(
        select(Prueba).where(Prueba.project_id == project_id).order_by(Prueba.id.desc())
    ).scalars()
    return [
        {"id": p.id, "nombre": p.definicion.get("name"), "origen": p.origen, "estado": p.estado,
         "version": p.version, "revision": p.revision,
         "actualizada_en": p.actualizada_en.isoformat() if p.actualizada_en else None}
        for p in filas
    ]


@router.post("/proyectos/{project_id}/pruebas", status_code=status.HTTP_201_CREATED)
def crear(project_id: int, body: NuevaPruebaIn, db: Session = Depends(get_db), user: User = Depends(require_staff)) -> dict:
    _proyecto(db, user, project_id)
    return _salida(_regla(lambda: servicio.crear_prueba(db, project_id, body.origen, body.tributario, user.email)))


@router.get("/pruebas/{prueba_id}")
def leer(prueba_id: int, db: Session = Depends(get_db), user: User = Depends(require_staff)) -> dict:
    p = _prueba(db, user, prueba_id)
    return {
        **_salida(p),
        "eventos": [
            {"accion": e.accion, "estado_anterior": e.estado_anterior, "estado_nuevo": e.estado_nuevo,
             "actor": e.actor, "comentario": e.comentario, "revision": e.revision,
             "fecha": e.creado_en.isoformat() if e.creado_en else None}
            for e in servicio.eventos(db, p.id)
        ],
    }


@router.post("/pruebas/{prueba_id}/acciones")
def accion(prueba_id: int, body: AccionIn, db: Session = Depends(get_db), user: User = Depends(require_staff)) -> dict:
    p = _prueba(db, user, prueba_id)
    return _salida(_regla(lambda: servicio.aplicar_accion(db, p, body.accion, body.revision, body.datos, user.email)))


@router.put("/fichas/{ficha_id}/definicion")
def guardar_definicion(ficha_id: int, body: DefinicionIn, db: Session = Depends(get_db), user: User = Depends(require_staff)) -> dict:
    ficha = db.get(NiifFicha, ficha_id)
    if ficha is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Ficha no encontrada.")
    try:
        servicio.guardar_definicion_ficha(db, ficha, body.definicion, body.filas)
    except ReglaIncumplida as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))
    except (ValueError, KeyError, ArithmeticError, StopIteration) as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e) or "La definición no se pudo ejecutar.")
    return {"id": ficha.id, "definicion_guardada": True}
