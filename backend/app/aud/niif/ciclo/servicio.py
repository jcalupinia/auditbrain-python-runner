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

import hashlib
import re

from backend.app.aud.niif.ciclo import almacen, datos, reglas
# Dentro de aplicar_accion el parámetro `datos` (cuerpo de la acción) tapa al
# módulo: ahí se usa este alias.
from backend.app.aud.niif.ciclo import datos as datos_mod
from backend.app.aud.niif.ciclo.models import FichaEncargo, Prueba, PruebaArchivo, PruebaEvento
from backend.app.aud.niif.requerimiento import check_upload
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
            return datos.validate_definition({**copy.deepcopy(f.definicion), "id": "custom"})
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
    elif accion == "generate_request":
        p.estado = reglas.transicion(t, accion)
        reg["requests"] = datos_mod.create_requests(reg["program"], reg["engagement"]["cutoff"], p.definicion)

    elif accion in ("save_request", "approve_request"):
        if p.estado != "REQUERIMIENTO_GENERADO":
            raise ReglaIncumplida("Requerimientos no editables.")
        reqs = datos.get("requests")
        if not isinstance(reqs, list) or not reqs or len(reqs) > 100:
            raise ReglaIncumplida("Defina requerimientos.")
        codigos = {x["code"] for x in reg["program"]}
        for r in reqs:
            if not isinstance(r, dict) or not r.get("id") or not str(r.get("document") or "").strip() \
                    or not str(r.get("purpose") or "").strip() or r.get("procedure") not in codigos:
                raise ReglaIncumplida("Complete cada requerimiento y vincule un procedimiento aprobado.")
        if len({r["id"] for r in reqs}) != len(reqs):
            raise ReglaIncumplida("Identificadores duplicados.")
        reg["requests"] = [{**r, "status": "PENDIENTE"} for r in reqs]
        if accion == "approve_request":
            p.estado = reglas.transicion({**reg, "state": p.estado}, accion)

    elif accion == "reject_file":
        # En el sitio el rechazo se envía al validar; aquí queda guardado en el
        # archivo para que otro auditor lo vea. La regla de cobertura es la misma.
        if p.estado not in ("REQUERIMIENTO_APROBADO", "DOCUMENTACION_RECIBIDA"):
            raise ReglaIncumplida("La documentación ya fue validada.")
        fid = datos.get("fileId")
        a = db.get(PruebaArchivo, int(fid)) if str(fid or "").isdigit() else None
        if a is None or a.prueba_id != p.id:
            raise ReglaIncumplida("Archivo no encontrado.")
        a.estado = "recibido" if a.estado == "rechazado" else "rechazado"
        datos = {**datos, "comment": f"{a.requerimiento}: {a.nombre} → {a.estado}"}

    elif accion == "map_validate":
        if p.estado not in ("REQUERIMIENTO_APROBADO", "DOCUMENTACION_RECIBIDA"):
            raise ReglaIncumplida("Datos bloqueados después de validar.")

        def hoja(file_id, nombre):
            a = db.get(PruebaArchivo, int(file_id)) if str(file_id or "").isdigit() else None
            if a is None or a.prueba_id != p.id:
                raise ReglaIncumplida("Archivo no encontrado.")
            leido = datos_mod.read_spreadsheet(almacen.leer(a.ruta), a.nombre)
            sheet = next((x for x in leido["sheets"] if x["name"] == nombre), None)
            if sheet is None:
                raise ReglaIncumplida("Seleccione una hoja válida.")
            return a, sheet

        archivo, sheet = hoja(datos.get("fileId"), datos.get("sheet"))
        mapped = datos_mod.mapped_rows(sheet, datos.get("header"), datos.get("mapping") or {}, p.definicion,
                                       {"id": archivo.id, "name": archivo.nombre})
        reg["rows"] = mapped["rows"]
        reg["mapping"] = {"fileId": archivo.id, "file": archivo.nombre, "sheet": datos.get("sheet"),
                          "header": datos.get("header"), "fields": datos.get("mapping"),
                          "headers": mapped["headers"], "blankRows": mapped["blankRows"]}
        if "flows" in p.definicion:
            flujos = datos.get("flows") if isinstance(datos.get("flows"), list) else []
            if datos.get("flowsFile"):
                fa, fs = hoja(datos.get("flowsFile"), datos.get("flowsSheet"))
                m = datos_mod.mapped_rows(fs, datos.get("flowsHeader"), datos.get("flowsMapping") or {},
                                          {"fields": FLOW_FIELDS}, {"id": fa.id, "name": fa.nombre})
                flujos = [{"id": x["id"], "fecha": x["fecha"], "importe": x["importe"]} for x in m["rows"]]
                reg["flowsMapping"] = {"fileId": fa.id, "file": fa.nombre, "sheet": datos.get("flowsSheet"),
                                       "header": datos.get("flowsHeader"), "fields": datos.get("flowsMapping"),
                                       "headers": m["headers"], "blankRows": m["blankRows"]}
            reg["flows"] = datos_mod.validate_flows(flujos)
        reg["validation"] = datos_mod.validate_rows(p.definicion, reg["rows"])
        p.estado = "DOCUMENTACION_RECIBIDA"
        reg["run"] = None
        if reg["validation"]["ok"]:
            reg["controlTotal"] = datos_mod.control_total(p.definicion, reg["rows"])

    elif accion == "validate":
        if datos.get("evidenceReviewed") is not True or len(str(datos.get("evidenceReview") or "").strip()) < 10:
            raise ReglaIncumplida(
                "Revise los originales, las extracciones y su relación con los datos; documente la revisión de evidencia."
            )
        reg["evidenceReview"] = {"by": actor, "at": _ahora_iso(), "text": str(datos["evidenceReview"])[:10000]}
        recibidos_ = archivos(db, p.id)
        docs = [{"id": a.id, "requestId": a.requerimiento, "component": a.componente} for a in recibidos_]
        rechazados = [a.id for a in recibidos_ if a.estado == "rechazado"]
        faltan = datos_mod.tool_gaps(reg["requests"], docs, rechazados)
        if faltan:
            raise ReglaIncumplida("Cobertura incompleta. " + " · ".join(faltan))
        reg["rejectedFiles"] = rechazados
        reg["reconciliation"] = datos_mod.reconcile(
            reg.get("controlTotal"), datos.get("ledger"), datos.get("tolerance"), str(datos.get("acceptance") or "")
        )
        p.estado = reglas.transicion({**reg, "state": p.estado}, accion)
        con_archivo = {a.requerimiento for a in recibidos_}
        reg["requests"] = [{**r, "status": "RECIBIDO" if r["id"] in con_archivo else "NO REQUERIDO"} for r in reg["requests"]]

    else:
        raise ReglaIncumplida("Acción no disponible en el estado actual.")

    p.registro = reg
    p.revision += 1
    _evento(db, p, accion, anterior, actor, str(datos.get("comment") or ""))
    db.commit()
    db.refresh(p)
    return p


# --- evidencia ---------------------------------------------------------------

FLOW_FIELDS = [
    {"key": "id", "label": "Contrato", "type": "text"},
    {"key": "fecha", "label": "Fecha del pago", "type": "date"},
    {"key": "importe", "label": "Importe", "type": "number"},
]


def invalidar(reg: dict, razon: str) -> dict:
    """Puerto de ``invalidateData`` (lifecycle.ts): la evidencia nueva obliga a
    volver a mapear y validar; se borra todo lo que dependía de los datos."""
    return {**reg, "rows": [], "mapping": None, "flows": None, "flowsMapping": None, "validation": None,
            "reconciliation": None, "run": None, "runHash": None, "controlTotal": None, "analysis": "",
            "conclusion": "", "conclusionReviewed": False, "exceptionReview": "", "notes": [], "artifacts": None,
            "templateApproved": None, "analysisAgent": None, "executedAt": None, "approvedAt": None,
            "approvedBy": None, "invalidatedAt": _ahora_iso(), "invalidationReason": razon}


def archivos(db: Session, prueba_id: int) -> list[PruebaArchivo]:
    return list(db.execute(
        select(PruebaArchivo).where(PruebaArchivo.prueba_id == prueba_id).order_by(PruebaArchivo.id)
    ).scalars())


def subir_archivo(db: Session, p: Prueba, revision: int, requerimiento: str, componente: str,
                  nombre: str, contenido: bytes, actor: str) -> PruebaArchivo:
    """Puerto de POST /api/tool-files del sitio, sobre el disco del portal."""
    if revision != p.revision:
        raise Conflicto("La prueba cambió mientras la editaba. Actualice y vuelva a intentarlo.")
    if p.estado not in ("REQUERIMIENTO_APROBADO", "DOCUMENTACION_RECIBIDA"):
        raise ReglaIncumplida("La carga no está habilitada en esta etapa.")
    reg = copy.deepcopy(p.registro)
    if not any(r["id"] == requerimiento for r in reg["requests"]):
        raise ReglaIncumplida("Vincule un requerimiento aprobado.")
    try:
        check_upload(datos.requests_as_items(reg["requests"]), requerimiento, componente or None, nombre)
    except ValueError as e:
        raise ReglaIncumplida(str(e))
    if not contenido or len(contenido) > almacen.MAX_ARCHIVO:
        raise ReglaIncumplida("Seleccione un archivo de hasta 25 MB.")
    ext = nombre.rsplit(".", 1)[-1].lower() if "." in nombre else ""
    if ext not in almacen.TIPOS:
        raise ReglaIncumplida("Use XLSX, DOCX, CSV, XML, PDF, TXT, MD, ZIP, PNG, JPG o WebP.")
    limpio = re.sub(r"[\x00-\x1f/\\]", "_", nombre)[:180]
    huella = hashlib.sha256(contenido).hexdigest()
    try:
        ruta = almacen.guardar(p.id, f"{len(archivos(db, p.id)) + 1:04d}_{huella[:16]}.{ext}", contenido)
    except almacen.SinEspacio as e:
        raise ReglaIncumplida(str(e))
    a = PruebaArchivo(prueba_id=p.id, requerimiento=requerimiento, componente=componente or None, nombre=limpio,
                      tipo=almacen.TIPOS[ext], tamano=len(contenido), sha256=huella, ruta=ruta, subido_por=actor)
    db.add(a)
    anterior = p.estado
    reg = invalidar(reg, "Se incorporó nueva evidencia. Vuelva a mapear y validar la población.")
    reg["evidenceReview"] = None
    p.registro = reg
    p.estado = "DOCUMENTACION_RECIBIDA"
    p.revision += 1
    _evento(db, p, "upload", anterior, actor, f"{requerimiento}{' · ' + componente if componente else ''}: {limpio}")
    db.commit()
    db.refresh(a)
    return a


def eventos(db: Session, prueba_id: int) -> list[PruebaEvento]:
    return list(db.execute(
        select(PruebaEvento).where(PruebaEvento.prueba_id == prueba_id).order_by(PruebaEvento.id)
    ).scalars())


# --- definición probada de una ficha NIIF -----------------------------------

def guardar_definicion_ficha(db: Session, ficha: NiifFicha, definicion: dict, filas: list[dict],
                             parametros: dict | None = None) -> NiifFicha:
    """Guarda la definición que corrió en el Estudio.

    Se vuelve a ejecutar aquí con el motor Python: no basta con que el
    navegador diga que corrió.
    """
    from backend.app.aud.niif import estudio

    if ficha.estado == "enviada":
        raise ReglaIncumplida("La ficha ya fue enviada al catálogo: su definición no se modifica.")
    datos.validate_definition({**definicion, "id": "custom"})
    estudio.ejecutar_definicion(definicion, filas, parametros or {})
    ficha.definicion = definicion
    db.commit()
    db.refresh(ficha)
    return ficha
