"""Operaciones del ciclo de una prueba (E6: ficha del encargo, creación y programa).

Las reglas están en ``reglas.py`` (portadas del sitio y vigiladas por el
espejo). Aquí va lo que el sitio hace en ``app/api/tools/route.ts`` alrededor de
esas reglas: armar el registro inicial, aplicar cada acción, llevar la
bitácora y la concurrencia.
"""
from __future__ import annotations

import copy
import datetime
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.aud.niif.ciclo import reglas
from backend.app.aud.niif.ciclo.models import FichaEncargo, Prueba, PruebaEvento
from backend.app.aud.niif.ciclo.reglas import ReglaIncumplida
from backend.app.aud.niif.models import NiifFicha

VERSIONES = json.loads((Path(__file__).resolve().parent / "versiones.json").read_text(encoding="utf-8"))

# Fichas NIIF que ya se pueden aplicar a un cliente: probadas o enviadas, y con
# la definición que corrió en su Estudio.
ESTADOS_FICHA_USABLE = ("probada", "enviada")


class Conflicto(Exception):
    """La prueba cambió desde que se leyó (revisión distinta)."""


def _ahora_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


# --- ficha del encargo -------------------------------------------------------

def leer_ficha(db: Session, project_id: int) -> dict | None:
    f = db.get(FichaEncargo, project_id)
    return f.datos if f else None


def guardar_ficha(db: Session, project_id: int, datos: dict, actor: str) -> dict:
    limpia = reglas.validar_ficha_encargo(datos, completa=True)
    f = db.get(FichaEncargo, project_id)
    if f is None:
        f = FichaEncargo(project_id=project_id, datos=limpia, actualizada_por=actor)
        db.add(f)
    else:
        f.datos = limpia
        f.actualizada_por = actor
    db.commit()
    return limpia


# --- herramientas disponibles ------------------------------------------------

def herramientas_disponibles(db: Session) -> list[dict]:
    """Catálogo del sitio más las fichas NIIF con definición probada."""
    lista = [
        {"origen": k, "nombre": d["name"], "area": d["area"], "tipo": "catálogo"}
        for k, d in reglas.CATALOGO.items()
    ]
    fichas = db.execute(
        select(NiifFicha).where(NiifFicha.estado.in_(ESTADOS_FICHA_USABLE)).order_by(NiifFicha.nombre)
    ).scalars()
    for f in fichas:
        if f.definicion:
            lista.append({"origen": f"ficha:{f.id}", "nombre": f.nombre, "area": f.rubro, "tipo": "ficha NIIF"})
    return lista


def _definicion_de(db: Session, origen: str) -> dict:
    if origen in reglas.CATALOGO:
        return copy.deepcopy(reglas.CATALOGO[origen])
    if origen.startswith("ficha:") and origen[6:].isdigit():
        f = db.get(NiifFicha, int(origen[6:]))
        if f and f.estado in ESTADOS_FICHA_USABLE and f.definicion:
            # Toda definición que no es del catálogo corre como «custom», igual
            # que en el sitio (validateDefinition({...definition, id:'custom'})).
            return {**copy.deepcopy(f.definicion), "id": "custom"}
    raise ReglaIncumplida("Seleccione una herramienta.")


# --- pruebas -----------------------------------------------------------------

def _evento(db: Session, p: Prueba, accion: str, anterior: str | None, actor: str, comentario: str = "") -> None:
    db.add(PruebaEvento(
        prueba_id=p.id, revision=p.revision, accion=accion, estado_anterior=anterior,
        estado_nuevo=p.estado, actor=actor, comentario=comentario or None,
    ))


def crear_prueba(db: Session, project_id: int, origen: str, tributario: bool, actor: str) -> Prueba:
    """Registro inicial igual al del sitio (POST /api/tools)."""
    encargo = leer_ficha(db, project_id)
    if not encargo:
        raise ReglaIncumplida("Complete primero la ficha del encargo.")
    d = _definicion_de(db, origen)
    if d["id"] == "pce" and encargo["framework"] != "NIIF completas":
        raise ReglaIncumplida(
            "La matriz PCE de este catálogo corresponde a NIIF completas. "
            "Para PYMES defina y apruebe una metodología específica."
        )
    pais = encargo.get("country") or ""
    if not 2 <= len(pais) <= 80:
        raise ReglaIncumplida("Seleccione el país del encargo.")
    registro = {
        "methodologyVersion": VERSIONES["methodologyVersion"],
        "contextOverride": encargo.get("reuseScope") in ("one", "selected"),
        "engagement": encargo,
        "country": pais,
        "taxApplicable": bool(tributario),
        "taxScope": "",
        "program": [],
        "sources": reglas.fuentes_oficiales(d, encargo["framework"], pais, bool(tributario)),
        "sourcesVerified": False,
        "requests": [],
        "rows": [],
        "parameters": {"cutoff": encargo["cutoff"], "buckets": []},
        "notes": [],
        "analysis": "",
        "conclusion": "",
        "conclusionReviewed": False,
        "createdAt": _ahora_iso(),
        "createdBy": actor,
    }
    p = Prueba(
        project_id=project_id, version=1, estado="PRUEBA_SELECCIONADA", origen=origen,
        definicion=d, registro=registro, revision=1, creada_por=actor,
    )
    db.add(p)
    db.flush()
    _evento(db, p, "create", None, actor)
    db.commit()
    db.refresh(p)
    return p


def _t(p: Prueba) -> dict:
    """El registro con la forma que esperan las reglas del sitio."""
    return {**p.registro, "state": p.estado, "definition": p.definicion}


def aplicar_accion(db: Session, p: Prueba, accion: str, revision: int, datos: dict, actor: str) -> Prueba:
    """Acciones de E6. Cada rama replica la del mismo nombre en route.ts."""
    if revision != p.revision:
        raise Conflicto("La prueba cambió mientras la editaba. Actualice y vuelva a intentarlo.")
    t = _t(p)
    reg = copy.deepcopy(p.registro)
    anterior = p.estado

    if accion == "research":
        if p.estado not in ("PRUEBA_SELECCIONADA", "PROGRAMA_PROPUESTO"):
            raise ReglaIncumplida("La investigación está cerrada en esta versión.")
        # Diseño §7: se proponen las fuentes oficiales; la consulta automática
        # de esas páginas queda para una fase posterior. Como en el sitio, las
        # fuentes se reemplazan y hay que volver a verificarlas.
        reg["sources"] = reglas.fuentes_oficiales(p.definicion, reg["engagement"]["framework"], reg["country"], reg["taxApplicable"])
        reg["researchedAt"] = _ahora_iso()
        reg["sourcesVerified"] = False

    elif accion == "generate_program":
        if not reg.get("researchedAt"):
            raise ReglaIncumplida("Consulte primero las fuentes oficiales.")
        p.estado = reglas.transicion(t, accion)
        reg["program"] = reglas.crear_programa(p.definicion, reg["engagement"])

    elif accion in ("save_program", "approve_program"):
        if p.estado != "PROGRAMA_PROPUESTO":
            raise ReglaIncumplida("Programa no editable en esta etapa.")
        programa, fuentes = datos.get("program"), datos.get("sources")
        reglas.validar_programa(programa, fuentes)
        reg["program"], reg["sources"] = programa, fuentes
        reg["taxScope"] = str(datos.get("taxScope") or "")[:10000]
        reg["sourcesVerified"] = False
        if accion == "approve_program":
            reglas.validar_ficha_encargo({**reg["engagement"], "country": reg["country"]}, completa=True)
            reg["sourcesVerified"] = reglas.verificar_fuentes(reg)
            aprobado = reglas.vincular_fuentes(reg)
            p.estado = reglas.transicion({**reg, "state": p.estado}, accion)
            reg["program"] = aprobado
    else:
        raise ReglaIncumplida("Acción no disponible en el estado actual.")

    p.registro = reg
    p.revision += 1
    _evento(db, p, accion, anterior, actor, str(datos.get("comment") or ""))
    db.commit()
    db.refresh(p)
    return p


def eventos(db: Session, prueba_id: int) -> list[PruebaEvento]:
    return list(db.execute(
        select(PruebaEvento).where(PruebaEvento.prueba_id == prueba_id).order_by(PruebaEvento.id)
    ).scalars())


# --- definición probada de una ficha NIIF -----------------------------------

def guardar_definicion_ficha(db: Session, ficha: NiifFicha, definicion: dict, filas: list[dict]) -> NiifFicha:
    """Guarda la definición que corrió en el Estudio.

    Se vuelve a ejecutar aquí con el motor Python: no basta con que el
    navegador diga que corrió.
    """
    from backend.app.aud.niif import estudio

    if ficha.estado == "enviada":
        raise ReglaIncumplida("La ficha ya fue enviada al catálogo: su definición no se modifica.")
    estudio.ejecutar_definicion(definicion, filas)
    ficha.definicion = definicion
    db.commit()
    db.refresh(ficha)
    return ficha
