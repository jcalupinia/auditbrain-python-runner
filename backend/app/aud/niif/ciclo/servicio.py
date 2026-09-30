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

from sqlalchemy import func, select
from sqlalchemy.orm import Session

import hashlib
import re
import uuid

from backend.app.aud.niif.ciclo import almacen, datos, reglas
# Dentro de aplicar_accion el parámetro `datos` (cuerpo de la acción) tapa al
# módulo: ahí se usa este alias.
from backend.app.aud.niif.ciclo import datos as datos_mod
from backend.app.aud.niif.ciclo.models import FichaEncargo, Prueba, PruebaArchivo, PruebaEvento, RegistroEncargo
from backend.app.aud.niif.requerimiento import check_upload
from backend.app.aud.niif.ciclo.reglas import ReglaIncumplida
from backend.app.aud.niif.models import NiifFicha
from backend.app.aud.niif import procesadores
from backend.app.aud.niif.procesadores import libro

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

def pruebas_de(definicion: dict) -> list[str]:
    """Lo que prueba la herramienta, para su tarjeta en Auditoría externa · Análisis: el objetivo de cada procedimiento de
    su programa (depreciación, deterioro, desmantelamiento…), sin los códigos de requisito entre paréntesis."""
    out: list[str] = []
    for p in definicion.get("program") or []:
        t = re.sub(r"\s*\([^()]*\)\s*$", "", str((p or {}).get("objective") or "")).strip()
        if t and t not in out:
            out.append(t)
    return out


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
            # `estado` separa lo publicado en el catálogo («enviada») de lo que aún
            # espera aprobación («probada»); `marcos` dice a qué marco sirve.
            lista.append({"origen": f"ficha:{f.id}", "nombre": f.nombre, "area": f.rubro, "tipo": "ficha NIIF",
                          "estado": f.estado, "marcos": f.definicion.get("frameworks") or [],
                          "resumen": f.definicion.get("summary") or "", "pruebas": pruebas_de(f.definicion)})
    # Herramientas fabricadas directamente en el catálogo: cada procesador con RUBRO aparece en la
    # tarjeta de su rubro sin pasar por «Diseñar fichas» (decisión del dueño, 2026-09-22).
    for pid, mod in procesadores.PROCESADORES.items():
        if getattr(mod, "RUBRO", None):
            d = mod.definicion()
            lista.append({"origen": f"proc:{pid}", "nombre": d["name"], "area": mod.RUBRO, "tipo": "herramienta NIIF",
                          "estado": getattr(mod, "ESTADO", "probada"), "marcos": d.get("frameworks") or [],
                          "resumen": d.get("summary") or "", "pruebas": pruebas_de(d)})
    return lista


def _definicion_de(db: Session, origen: str) -> dict:
    if origen in reglas.CATALOGO:
        return copy.deepcopy(reglas.CATALOGO[origen])
    if origen.startswith("proc:"):
        mod = procesadores.PROCESADORES.get(origen[5:])
        if mod is not None and getattr(mod, "RUBRO", None):
            return _definicion_procesador({**mod.definicion(), "id": "custom"})
    if origen.startswith("ficha:") and origen[6:].isdigit():
        f = db.get(NiifFicha, int(origen[6:]))
        if f and f.estado in ESTADOS_FICHA_USABLE and f.definicion:
            if f.definicion.get("processor"):
                return _definicion_procesador({**copy.deepcopy(f.definicion), "id": "custom"})
            # Toda definición que no es del catálogo corre como «custom», igual
            # que en el sitio (validateDefinition({...definition, id:'custom'})).
            return datos.validate_definition({**copy.deepcopy(f.definicion), "id": "custom"})
    raise ReglaIncumplida("Seleccione una herramienta.")


def _definicion_procesador(d: dict) -> dict:
    """Definición de una ficha con procesador especializado: el cálculo no es
    declarativo, así que se valida con su procesador y con el plan (programa y
    requerimientos) igual que cualquier ficha."""
    try:
        procesadores.de(d).validar_definicion(d)
    except ValueError as e:
        raise ReglaIncumplida(str(e))
    datos._validar_plan(d)
    # Base legal tributaria sugerida por herramienta (viaja con la ficha): pre-llena
    # el recuadro «Tratamiento tributario revisado y su sustento» en la vista.
    from backend.app.aud.niif import base_legal
    sugerida = base_legal.sugerencia(d.get("processor"))
    if sugerida is not None:
        d["tributario_sugerido"] = sugerida
    return d


def _num_seguro(v) -> float:
    n = procesadores.perdidas_incurridas_s11.a_num(v)
    return n or 0.0


def _auto_extraer_ia(db: Session, p: Prueba, reg: dict, proc) -> list[str]:
    """Al procesar: extrae por IA los documentos PDF/Word de los requerimientos
    extraíbles (carta/informe/notas) que aún NO tengan extracción, y los deja en
    ``reg["extraccion"]`` marcados como automáticos y pendientes de revisión. Respeta
    lo ya extraído/confirmado con el botón. Devuelve avisos legibles (uno por archivo).
    Nunca crashea: si la IA no está disponible o falla, avisa y sigue (el requerimiento
    es opcional; el auditor puede subir la tabla en Excel/CSV)."""
    extdatasets = getattr(proc, "EXTRACCION_DATASETS", ())
    if not extdatasets:
        return []
    from backend.app.aud.niif.ciclo import extraccion_ia

    por_req = {r["id"]: r for r in (reg.get("requests") or []) if r.get("dataset") in extdatasets}
    extraccion = dict(reg.get("extraccion") or {})
    corte = (reg.get("engagement") or {}).get("cutoff", "")
    avisos: list[str] = []
    for a in archivos(db, p.id):
        if a.estado == "rechazado" or a.requerimiento not in por_req or str(a.id) in extraccion:
            continue
        if extraccion_ia._extension(a.nombre) not in ("pdf", "docx"):
            continue
        ds = por_req[a.requerimiento]["dataset"]
        campos = proc.CAMPOS[proc.kind(ds)]
        enums = getattr(proc, "EXTRACCION_ENUMS", {}).get(ds, {})
        instr = getattr(proc, "EXTRACCION_INSTRUCCIONES", {}).get(ds, "")
        try:
            texto = extraccion_ia.texto_de_documento(a.nombre, almacen.leer(a.ruta))
            res = extraccion_ia.extraer_filas(campos, texto, enums=enums, instrucciones=instr,
                                              contexto=f"Corte de la auditoría: {corte}".strip())
        except extraccion_ia.ExtraccionError as e:
            avisos.append(f"{a.requerimiento} · no se pudo extraer «{a.nombre}» por IA ({e}); "
                          "súbalo en Excel/CSV o revise el documento.")
            continue
        v = proc.validar_filas(proc.kind(ds), res["rows"])
        extraccion[str(a.id)] = {"dataset": ds, "requestId": a.requerimiento, "file": a.nombre, "rows": res["rows"],
                                 "modelo": res["modelo"], "validation": v, "auto": True, "revisado": False,
                                 "at": _ahora_iso()}
        avisos.append(f"{a.requerimiento} · {len(res['rows'])} fila(s) extraídas por IA de «{a.nombre}» al procesar; "
                      "revíselas (la IA solo transcribe lo que leyó).")
    reg["extraccion"] = extraccion
    return avisos


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
    if p.estado == "APROBADO":
        raise ReglaIncumplida("La versión aprobada es inmutable.")
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
            if reg.get("taxApplicable"):
                if not bool(datos.get("taxAcknowledged")):
                    raise ReglaIncumplida("Marque «Revisé la base legal sugerida y estoy conforme» antes de confirmar la base técnica.")
                sugerido = str((p.definicion.get("tributario_sugerido") or {}).get("texto") or "").strip()
                final = reg["taxScope"].strip()
                acepto = bool(sugerido) and final == sugerido
                reg["taxScopeMeta"] = {"aceptadaSugerencia": acepto, "editada": not acepto,
                                       "actor": actor, "fecha": _ahora_iso(),
                                       "resumen": ("aceptó la base legal sugerida tal cual" if acepto
                                                   else "editó el tratamiento tributario respecto de la sugerencia")}
                datos = {**datos, "comment": f"Tratamiento tributario: {reg['taxScopeMeta']['resumen']}."}
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

        proc = procesadores.de(p.definicion)
        if proc:
            conjuntos = datos.get("datasets") if isinstance(datos.get("datasets"), dict) else {}
            por_ds = {r["dataset"]: r for r in reg["requests"] if r.get("dataset")}
            principal = proc.PRINCIPAL
            if not conjuntos.get(principal):
                raise ReglaIncumplida("Suba el anexo de cartera del ejercicio corriente antes de procesar.")
            filas_ds, mapeos, errores, avisos = {}, [], [], []
            for ds, partes in conjuntos.items():
                if ds not in por_ds or not isinstance(partes, list) or len(partes) > 60:
                    raise ReglaIncumplida("Anexo no previsto en los requerimientos de la ficha.")
                campos = proc.CAMPOS[proc.kind(ds)]
                filas_ds.setdefault(ds, [])
                for parte in partes:
                    parte = parte if isinstance(parte, dict) else {}
                    archivo, sheet = hoja(parte.get("fileId"), parte.get("sheet"))
                    if archivo.estado == "rechazado" or archivo.requerimiento != por_ds[ds]["id"]:
                        raise ReglaIncumplida(f"{archivo.nombre} no corresponde a {por_ds[ds]['id']} o está rechazado.")
                    try:
                        m = proc.filas_mapeadas(sheet, parte.get("header"), parte.get("mapping") or {}, campos,
                                                {"id": archivo.id, "name": archivo.nombre})
                    except ValueError as e:
                        raise ReglaIncumplida(str(e))
                    filas_ds[ds] += m["rows"]
                    mapeos.append({"dataset": ds, "requestId": archivo.requerimiento, "fileId": archivo.id, "file": archivo.nombre,
                                   "sheet": parte.get("sheet"), "header": parte.get("header"), "fields": parte.get("mapping"),
                                   "headers": m["headers"], "blankRows": m["blankRows"], "records": len(m["rows"])})
            # Auto-extracción al procesar (decisión del dueño): si hay un PDF/Word en un
            # requerimiento extraíble (carta/informe/notas) que aún no tiene extracción,
            # la IA lo lee AHORA y se usa (queda marcado como automático, pendiente de
            # revisión del auditor). Si ya se extrajo/confirmó con el botón, se respeta.
            avisos += [{"row": None, "message": msg} for msg in _auto_extraer_ia(db, p, reg, proc)]
            # Filas extraídas por IA de la carta/informe/notas (PDF/Word), ya en
            # reg["extraccion"] (por el botón «Extraer con IA» o por la auto-extracción
            # de arriba). Se suman a su dataset.
            for fid, info in (reg.get("extraccion") or {}).items():
                ds = info.get("dataset")
                filas = info.get("rows") or []
                if ds not in por_ds or not filas:
                    continue
                base = len(filas_ds.setdefault(ds, []))
                nuevas = [{**f, "_row": base + j + 1} for j, f in enumerate(filas)]
                filas_ds[ds] += nuevas
                mapeos.append({"dataset": ds, "requestId": info.get("requestId"), "file": info.get("file"),
                               "fileId": int(fid) if str(fid).isdigit() else None, "source": "ia",
                               "modelo": info.get("modelo"), "records": len(nuevas)})
            if sum(len(x) for x in filas_ds.values()) > datos_mod.MAX_ROWS:
                raise ReglaIncumplida(f"Cargue entre 1 y {datos_mod.MAX_ROWS} registros.")
            for ds, filas in filas_ds.items():
                v = proc.validar_filas(proc.kind(ds), filas)
                rid = por_ds[ds]["id"]
                errores += [{**e, "message": f"{rid} · {e['message']}"} for e in v["errors"]]
                avisos += [{**w, "message": f"{rid} · {w['message']}"} for w in v["warnings"]]
            reg["datasets"] = filas_ds
            reg["rows"] = filas_ds.get(principal, [])
            reg["mapping"] = mapeos[0] if mapeos else None
            reg["mappings"] = mapeos
            reg["validation"] = {"records": len(reg["rows"]), "errors": errores, "warnings": avisos, "ok": not errores}
            p.estado = "DOCUMENTACION_RECIBIDA"
            reg["run"] = None
            if not errores:
                control = getattr(proc, "CONTROL", "saldo")
                reg["controlTotal"] = procesadores.perdidas_incurridas_s11.r2(sum(_num_seguro(f.get(control)) for f in filas_ds[principal]))
            p.registro = reg
            p.revision += 1
            _evento(db, p, accion, anterior, actor, str(datos.get("comment") or ""))
            db.commit()
            db.refresh(p)
            return p

        # E10: la población puede venir en varios archivos del mismo formato
        # (un mes, una bodega por archivo): `files` los une en una sola, y cada
        # fila conserva su archivo y su parte. Un solo archivo sigue como en el sitio.
        partes = datos.get("files") if isinstance(datos.get("files"), list) and datos.get("files") else [
            {"fileId": datos.get("fileId"), "sheet": datos.get("sheet"), "header": datos.get("header"),
             "mapping": datos.get("mapping")}]
        if len(partes) > 60:
            raise ReglaIncumplida("Máximo 60 archivos por población.")
        filas, mapeos = [], []
        for parte in partes:
            parte = parte if isinstance(parte, dict) else {}
            archivo, sheet = hoja(parte.get("fileId"), parte.get("sheet"))
            if archivo.estado == "rechazado":
                raise ReglaIncumplida(f"{archivo.nombre} está rechazado: no entra en la población.")
            mapped = datos_mod.mapped_rows(sheet, parte.get("header"), parte.get("mapping") or {}, p.definicion,
                                           {"id": archivo.id, "name": archivo.nombre})
            for f in mapped["rows"]:
                if archivo.componente:
                    f["_component"] = archivo.componente
            filas += mapped["rows"]
            mapeos.append({"fileId": archivo.id, "file": archivo.nombre, "component": archivo.componente,
                           "sheet": parte.get("sheet"), "header": parte.get("header"), "fields": parte.get("mapping"),
                           "headers": mapped["headers"], "blankRows": mapped["blankRows"], "records": len(mapped["rows"])})
        if len(filas) > datos_mod.MAX_ROWS:
            raise ReglaIncumplida(f"Cargue entre 1 y {datos_mod.MAX_ROWS} registros.")
        reg["rows"] = filas
        reg["mapping"] = mapeos[0]
        reg["mappings"] = mapeos
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

    # --- E8: ejecución y análisis (route.ts: configure … save_analysis) --------
    elif accion == "configure" and procesadores.de(p.definicion):
        proc = procesadores.de(p.definicion)
        crudos = datos.get("parametros") if isinstance(datos.get("parametros"), dict) else {}
        params = {}
        for k in proc.PARAMETROS:
            v = crudos.get(k)
            if k == "tasas":
                tasas = {t: v[t] for t in (v or {}) if t in proc.NOMBRE_TRAMO and str(v[t]).strip() != ""} if isinstance(v, dict) else {}
                for t, x in tasas.items():
                    n = proc.a_num(x)
                    if n is None or not 0 <= n <= 100:
                        raise ReglaIncumplida(f"Tasa de {proc.NOMBRE_TRAMO[t]}: use un porcentaje entre 0 y 100.")
                params["tasas"] = {t: proc.a_num(x) for t, x in tasas.items()}
            elif v is not None and str(v).strip() != "" and isinstance(proc.PARAMETROS[k], str):
                params[k] = str(v).strip()[:300]          # parámetro de opción o texto
            elif v is not None and str(v).strip() != "":
                n = proc.a_num(v)
                if n is None or (n < 0 and k not in getattr(proc, "PARAM_NEGATIVOS", ())):
                    raise ReglaIncumplida(f"Parámetro {k}: use un número no negativo.")
                params[k] = n
        reg["parameters"] = {"cutoff": reg["engagement"]["cutoff"], "buckets": [],
                             "basis": str(datos.get("basis") or "").strip()[:10000], **params}
        if not reg["parameters"]["basis"]:
            raise ReglaIncumplida("Documente el sustento de parámetros y metodología.")
        p.estado = reglas.transicion({**reg, "state": p.estado}, "configure")

    elif accion == "configure":
        reg["parameters"] = {
            "cutoff": reg["engagement"]["cutoff"],
            "buckets": datos.get("buckets") if isinstance(datos.get("buckets"), list) else [],
            "basis": str(datos.get("basis") or "").strip()[:10000],
        }
        if not reg["parameters"]["basis"]:
            raise ReglaIncumplida("Documente el sustento de parámetros y metodología.")
        if p.definicion.get("id") == "pce":
            datos_mod.check_buckets(reg["parameters"])
        p.estado = reglas.transicion({**reg, "state": p.estado}, accion)

    elif accion == "approve_methodology":
        p.estado = reglas.transicion({**reg, "state": p.estado}, accion)

    elif accion == "execute":
        siguiente = reglas.transicion({**reg, "state": p.estado}, accion)
        # Aquí la autoridad es el motor Python (el mismo archivo del sitio); el
        # navegador corre domain.mjs y manda su resultado para contrastarlo.
        from backend.app.aud.niif import estudio
        proc = procesadores.de(p.definicion)
        try:
            if proc:
                # Procesador especializado: el cálculo solo existe en Python;
                # no hay resultado del navegador que contrastar.
                param = {k: v for k, v in reg["parameters"].items() if k in proc.PARAMETROS}
                # El marco y la edición del encargo enrutan el cálculo cuando la norma difiere (M02).
                param["_marco"] = reg["engagement"].get("framework") or ""
                param["_edicion"] = str(reg["engagement"].get("edition") or "")
                if getattr(proc, "USA_REGISTROS_ENCARGO", False):
                    # Independencia, aceptación, carta, discusión y comunicación registradas con un clic: se congelan en
                    # esta ejecución (la hoja 00_Registros del papel es la evidencia; NIA 230).
                    param["_encargo"] = registros_encargo(db, p.project_id)
                    # M4 (NIA 300 párr. 10): cifras y riesgos de la versión anterior, para el comparativo de la hoja 42.
                    anterior = version_anterior_run(db, p)
                    if anterior:
                        param["_anterior"] = anterior
                    # Audit trail (NIA 230, hoja 23): nombre y huella SHA-256 de cada archivo del cliente que se usó.
                    param["_archivos"] = archivos_de_entrada(db, p.id)
                run = proc.ejecutar(reg.get("datasets") or {}, param, reg["engagement"]["cutoff"])
                # La 3.ª edición de la NIIF para las PYMES rige desde el 1-1-2027: antes, solo con adopción anticipada.
                if "PYMES" in param["_marco"] and param["_edicion"] == "2025" and str(reg["engagement"]["cutoff"]) < "2027-01-01":
                    run["exceptions"] = [{"code": "PYMES_2025_ANTICIPADA", "amount": "0.00", "message":
                        "La NIIF para las PYMES 2025 (3.ª edición) rige para períodos desde el 1-1-2027: con corte "
                        f"{reg['engagement']['cutoff']} solo procede si la entidad la adoptó anticipadamente y lo revela; "
                        "de lo contrario use la edición 2015."}] + list(run.get("exceptions") or [])
                # Las cédulas y, dentro del libro, los datos que entregó el cliente (hojas D1_…).
                from backend.app.aud.niif.procesadores import datos_cliente
                run["hojas"] = datos_cliente.con_datos(proc, run, reg.get("datasets") or {})
                run["detalle"] = {k: v for k, v in run["detalle"].items() if k in ("tasas", "fiscal", "cortes")}
            else:
                run = estudio.ejecutar_definicion(p.definicion, reg["rows"], reg["parameters"], reg.get("flows") or [])
        except (ValueError, KeyError, ArithmeticError, StopIteration) as e:
            raise ReglaIncumplida(str(e) or "La prueba no se pudo ejecutar.")
        if not proc:
            run["exceptions"] = datos_mod.excepciones(p.definicion, run)
        motivo = "" if proc else datos_mod.motivo_contraste(run, datos.get("navegador"))
        if motivo:
            raise ReglaIncumplida(
                f"La ejecución del navegador no coincide con el motor Python ({motivo}). No se guardaron resultados."
            )
        reg["run"] = run
        reg["runHash"] = hashlib.sha256(json.dumps(
            {"definition": p.definicion, "rows": reg["rows"], "parameters": reg["parameters"],
             "flows": reg.get("flows") or [], "run": run},
            ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        reg["executedAt"] = _ahora_iso()
        p.estado = siguiente

    elif accion == "analyze":
        p.estado = reglas.transicion({**reg, "state": p.estado}, accion)
        reg["analysis"] = datos_mod.preliminary({**reg, "definition": p.definicion})

    elif accion in ("save_analysis", "submit"):
        if p.estado != "RESULTADOS_ANALIZADOS":
            raise ReglaIncumplida("Análisis no editable.")
        if not str(datos.get("analysis") or "").strip():
            raise ReglaIncumplida("Complete el análisis.")
        reg["analysis"] = str(datos["analysis"])[:50000]
        reg["conclusion"] = str(datos.get("conclusion") or "")[:20000]
        if accion == "submit":
            if not reg["conclusion"].strip():
                raise ReglaIncumplida("Redacte la conclusión preliminar antes de enviar.")
            p.estado = reglas.transicion({**reg, "state": p.estado, "definition": p.definicion}, accion)

    # --- E9: revisión y aprobación (route.ts) ---------------------------------
    elif accion == "return_to_data":
        if p.estado not in ("PRUEBA_CONFIGURADA", "METODOLOGIA_APROBADA", "PRUEBA_EJECUTADA",
                            "RESULTADOS_ANALIZADOS", "EN_REVISION") or len(str(datos.get("comment") or "").strip()) < 10:
            raise ReglaIncumplida("Un revisor debe documentar el motivo de reapertura.")
        p.estado = "DOCUMENTACION_RECIBIDA"
        ahora = _ahora_iso()
        reg.update(validation=None, reconciliation=None, run=None, runHash=None, analysis="", conclusion="",
                   conclusionReviewed=False, exceptionReview="")
        reg["notes"] = [{**n, "status": "ABIERTO", "response": "", "reopenedAt": ahora} for n in reg.get("notes") or []]

    elif accion == "add_note":
        if p.estado != "EN_REVISION":
            raise ReglaIncumplida("Solo revisores pueden crear puntos en revisión.")
        if not str(datos.get("comment") or "").strip():
            raise ReglaIncumplida("Describa el punto.")
        reg.setdefault("notes", []).append({
            "id": uuid.uuid4().hex, "section": str(datos.get("section") or "General")[:150],
            "comment": str(datos["comment"])[:6000], "createdBy": actor, "createdAt": _ahora_iso(),
            "response": "", "status": "ABIERTO",
        })

    elif accion in ("respond_note", "resolve_note"):
        if p.estado != "EN_REVISION":
            raise ReglaIncumplida("La herramienta no está en revisión.")
        nota = next((n for n in reg.get("notes") or [] if n.get("id") == datos.get("noteId")), None)
        if nota is None:
            raise ReglaIncumplida("Punto no encontrado.")
        if accion == "respond_note":
            if not str(datos.get("response") or "").strip():
                raise ReglaIncumplida("Escriba una respuesta sustentada.")
            nota.update(response=str(datos["response"])[:10000], respondedBy=actor, respondedAt=_ahora_iso(), status="RESPONDIDO")
        else:
            if nota.get("status") != "RESPONDIDO" or not str(nota.get("response") or "").strip():
                raise ReglaIncumplida("Un revisor debe resolver un punto respondido.")
            nota.update(status="RESUELTO", resolvedBy=actor, resolvedAt=_ahora_iso())

    elif accion == "approve":
        conclusion = str(datos.get("conclusion") or "")[:20000]
        if not conclusion.strip() or datos.get("conclusionReviewed") is not True:
            raise ReglaIncumplida("Revise y confirme la conclusión final.")
        reg["conclusion"] = conclusion
        reg["exceptionReview"] = str(datos.get("exceptionReview") or "").strip()
        if (reg.get("run") or {}).get("exceptions") and len(reg["exceptionReview"]) < 10:
            raise ReglaIncumplida("Documente la evaluación de excepciones antes de cerrar.")
        reg["conclusionReviewed"] = True
        # Una consulta técnica o diferencia de opinión abierta ya NO bloquea la aprobación (decisión del dueño,
        # 2026-09-29: que nada frene el avance). Si queda alguna abierta, se anota como advertencia en la bitácora.
        consultas_pend = consultas_abiertas(db, p.project_id) if getattr(procesadores.de(p.definicion), "USA_REGISTROS_ENCARGO", False) else 0
        p.estado = reglas.transicion({**reg, "state": p.estado, "definition": p.definicion}, accion)
        reg["approvedBy"] = actor
        reg["approvedAt"] = _ahora_iso()
        # NIA 220 (decisión del dueño, 2026-09-26): se permite aprobar el propio trabajo, pero queda advertido en el
        # registro, en la bitácora y en la carátula del papel.
        envio = next((e for e in reversed(eventos(db, p.id)) if e.accion == "submit"), None)
        reg["submittedBy"] = envio.actor if envio else ""
        reg["segregation"] = bool(envio) and envio.actor != actor
        if envio and envio.actor == actor:
            datos = {**datos, "comment": (SIN_SEGREGACION + " " + str(datos.get("comment") or "")).strip()}
        if consultas_pend:
            datos = {**datos, "comment": (f"Advertencia (NIA 220): se aprobó con {consultas_pend} consulta(s) o "
                                          "diferencia(s) de opinión abierta(s). " + str(datos.get("comment") or "")).strip()}
        # El papel final (Excel y HTML) lo arma el navegador con el exportador
        # del sitio desde este registro ya aprobado y lo sube a guardar_papel().
        reg["artifacts"] = None

    elif accion == "approve_template":
        if not reg.get("sourcesVerified") or p.estado in ("PRUEBA_SELECCIONADA", "PROGRAMA_PROPUESTO"):
            raise ReglaIncumplida("Apruebe el programa y sus fuentes antes del diseño.")
        parametros = {"cutoff": reg["engagement"]["cutoff"],
                      "buckets": datos.get("buckets") if isinstance(datos.get("buckets"), list) else [],
                      "basis": str(datos.get("basis") or "").strip()}
        if not parametros["basis"]:
            raise ReglaIncumplida("Sustente la metodología de la plantilla.")
        if p.definicion.get("id") == "pce":
            datos_mod.check_buckets(parametros)
        reg["templateApproved"] = {"by": actor, "at": _ahora_iso(), "parameters": parametros}

    elif accion in ("extraer_ia", "guardar_extraccion"):
        # Carta de control interno / informe del año anterior en PDF o Word: la IA
        # extrae la tabla (extraer_ia) y el auditor la revisa/edita y confirma
        # (guardar_extraccion). Las filas quedan en reg["extraccion"][fileId] y
        # map_validate las suma al dataset. No cambia el estado del circuito.
        proc = procesadores.de(p.definicion)
        if not proc:
            raise ReglaIncumplida("La extracción por IA solo aplica a las herramientas con procesador.")
        if p.estado not in ("REQUERIMIENTO_APROBADO", "DOCUMENTACION_RECIBIDA"):
            raise ReglaIncumplida("La documentación ya fue validada.")
        fid = datos.get("fileId")
        a = db.get(PruebaArchivo, int(fid)) if str(fid or "").isdigit() else None
        if a is None or a.prueba_id != p.id or a.estado == "rechazado":
            raise ReglaIncumplida("Archivo no encontrado.")
        req = next((r for r in reg.get("requests") or [] if r.get("id") == a.requerimiento and r.get("dataset")), None)
        ds = req.get("dataset") if req else None
        if ds not in getattr(proc, "EXTRACCION_DATASETS", ()):
            raise ReglaIncumplida("Este documento no admite extracción por IA.")
        campos = proc.CAMPOS[proc.kind(ds)]
        extraccion = dict(reg.get("extraccion") or {})
        if accion == "extraer_ia":
            from backend.app.aud.niif.ciclo import extraccion_ia
            enums = getattr(proc, "EXTRACCION_ENUMS", {}).get(ds, {})
            instr = getattr(proc, "EXTRACCION_INSTRUCCIONES", {}).get(ds, "")
            contexto = f"Corte de la auditoría: {reg.get('engagement', {}).get('cutoff', '')}".strip()
            try:
                texto = extraccion_ia.texto_de_documento(a.nombre, almacen.leer(a.ruta))
                res = extraccion_ia.extraer_filas(campos, texto, enums=enums, instrucciones=instr, contexto=contexto)
            except extraccion_ia.ExtraccionError as e:
                raise ReglaIncumplida(str(e))
            rows, modelo = res["rows"], res["modelo"]
        else:  # guardar_extraccion: la tabla que el auditor revisó y editó
            crudas = datos.get("rows")
            if not isinstance(crudas, list) or len(crudas) > datos_mod.MAX_ROWS:
                raise ReglaIncumplida("Filas inválidas.")
            claves = [c["key"] for c in campos]
            rows = [{**{k: (f.get(k) if isinstance(f, dict) else "") for k in claves}, "_row": i}
                    for i, f in enumerate(crudas, start=1)]
            modelo = (extraccion.get(str(a.id)) or {}).get("modelo", "")
        v = proc.validar_filas(proc.kind(ds), rows)
        extraccion[str(a.id)] = {"dataset": ds, "requestId": a.requerimiento, "file": a.nombre, "rows": rows,
                                 "modelo": modelo, "validation": v, "at": _ahora_iso()}
        reg["extraccion"] = extraccion
        datos = {**datos, "comment": f"{a.requerimiento}: {len(rows)} fila(s) "
                 + ("extraídas por IA de " if accion == "extraer_ia" else "confirmadas de ") + a.nombre
                 + ("" if v["ok"] else " (revisar avisos de validación)")}

    else:
        raise ReglaIncumplida("Acción no disponible en el estado actual.")

    p.registro = reg
    p.revision += 1
    _evento(db, p, accion, anterior, actor, str(datos.get("comment") or ""))
    db.commit()
    db.refresh(p)
    if accion == "approve" and procesadores.de(p.definicion):
        # El papel de un procesador lo arma el servidor (el exportador del sitio
        # no conoce sus cédulas): se guarda al aprobar, con su huella.
        return guardar_papel(db, p, p.revision, *papel_procesador(db, p), actor)
    return p


def _eventos_papel(db: Session, p: Prueba) -> list[dict]:
    evs = [{"fecha": e.creado_en.isoformat() if e.creado_en else "", "accion": e.accion, "estado_anterior": e.estado_anterior,
            "estado_nuevo": e.estado_nuevo, "actor": e.actor, "comentario": e.comentario or ""} for e in eventos(db, p.id)]
    return evs


def args_papel(db: Session, p: Prueba) -> tuple:
    return (p.definicion, p.registro, _eventos_papel(db, p), p.version, p.estado)


def papel_procesador(db: Session, p: Prueba) -> tuple[bytes, bytes]:
    args = args_papel(db, p)
    return libro.xlsx(*args), libro.html(*args)


# --- evidencia ---------------------------------------------------------------

FLOW_FIELDS = [
    {"key": "id", "label": "Contrato", "type": "text"},
    {"key": "fecha", "label": "Fecha del pago", "type": "date"},
    {"key": "importe", "label": "Importe", "type": "number"},
]


def invalidar(reg: dict, razon: str) -> dict:
    """Puerto de ``invalidateData`` (lifecycle.ts): la evidencia nueva obliga a
    volver a mapear y validar; se borra todo lo que dependía de los datos."""
    return {**reg, "rows": [], "datasets": None, "mapping": None, "flows": None, "flowsMapping": None, "validation": None,
            "reconciliation": None, "run": None, "runHash": None, "controlTotal": None, "analysis": "",
            "conclusion": "", "conclusionReviewed": False, "exceptionReview": "", "notes": [], "artifacts": None,
            "templateApproved": None, "analysisAgent": None, "executedAt": None, "approvedAt": None,
            "approvedBy": None, "invalidatedAt": _ahora_iso(), "invalidationReason": razon}


def archivos(db: Session, prueba_id: int) -> list[PruebaArchivo]:
    return list(db.execute(
        select(PruebaArchivo).where(PruebaArchivo.prueba_id == prueba_id).order_by(PruebaArchivo.id)
    ).scalars())


def archivos_de_entrada(db: Session, prueba_id: int) -> list[dict]:
    """Archivos del cliente vigentes (no rechazados) de la prueba, para el audit trail del papel."""
    return [{"requerimiento": a.requerimiento, "nombre": a.nombre, "sha256": a.sha256, "tamano": a.tamano,
             "subido_por": a.subido_por or "", "subido_en": a.subido_en.isoformat(timespec="seconds") if a.subido_en else ""}
            for a in archivos(db, prueba_id) if a.clase == "source" and a.estado != "rechazado"]


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


# --- consola de comunicación por prueba (chat auditable, NIA 230) -----------
# Un comentario es un evento de la bitácora (accion="comentario"): así queda en
# la cédula 12 del papel y es trazable. Se permite en cualquier estado, incluso
# aprobada: la comunicación del equipo no muta el papel. El asistente responde
# como un actor más ("AUDIT-IA"), y su respuesta es un borrador para el auditor.
ACTOR_ASISTENTE = "AUDIT-IA"


def comentar(db: Session, p: Prueba, texto: str, actor: str, accion: str = "comentario") -> PruebaEvento:
    """Agrega un comentario a la consola de la prueba (no cambia el estado)."""
    texto = (texto or "").strip()
    if not texto:
        raise ValueError("El comentario no puede estar vacío.")
    ev = PruebaEvento(
        prueba_id=p.id, revision=p.revision, accion=accion, estado_anterior=None,
        estado_nuevo=p.estado, actor=actor, comentario=texto[:8000] or None,
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev


def sugerencias_pruebas(db: Session, p: Prueba) -> dict:
    """Puente planificación → pruebas: de una prueba de PLANIFICACIÓN, la lista
    ordenada de pruebas del piloto a ejecutar (una por herramienta, con sus cuentas
    y riesgos). Recomputa la planificación porque el ``detalle`` guardado se poda a
    tasas/fiscal/cortes y no conserva las cuentas a revisar; reutiliza la misma
    inyección de parámetros del encargo que ``execute``."""
    from backend.app.aud.niif import puente

    proc = procesadores.de(p.definicion)
    if proc is None or getattr(proc, "RUBRO", None) != "PLANIFICACION":
        raise ReglaIncumplida("Las pruebas sugeridas solo se derivan de una prueba de planificación.")
    reg = copy.deepcopy(p.registro)
    param = {k: v for k, v in reg["parameters"].items() if k in proc.PARAMETROS}
    param["_marco"] = reg["engagement"].get("framework") or ""
    param["_edicion"] = str(reg["engagement"].get("edition") or "")
    if getattr(proc, "USA_REGISTROS_ENCARGO", False):
        param["_encargo"] = registros_encargo(db, p.project_id)
        anterior_run = version_anterior_run(db, p)
        if anterior_run:
            param["_anterior"] = anterior_run
        param["_archivos"] = archivos_de_entrada(db, p.id)
    try:
        run = proc.ejecutar(reg.get("datasets") or {}, param, reg["engagement"]["cutoff"])
    except (ValueError, KeyError, ArithmeticError, StopIteration) as e:
        raise ReglaIncumplida(str(e) or "La planificación no se pudo ejecutar.")
    return puente.sugerencias(run)


def conversacion(db: Session, prueba_id: int) -> list[dict]:
    """La bitácora como línea de tiempo para la consola: cada evento es un
    comentario del equipo/asistente (``tipo='comentario'``) o una marca del
    circuito (``tipo='sistema'``: cambios de estado, cargas, papel)."""
    salida = []
    for e in eventos(db, prueba_id):
        salida.append({
            "id": e.id,
            "tipo": "comentario" if e.accion == "comentario" else "sistema",
            "accion": e.accion,
            "actor": e.actor,
            "es_asistente": e.actor == ACTOR_ASISTENTE or (e.actor or "").startswith(ACTOR_ASISTENTE),
            "texto": e.comentario or "",
            "estado_nuevo": e.estado_nuevo,
            "revision": e.revision,
            "fecha": e.creado_en.isoformat() if e.creado_en else None,
        })
    return salida


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
    if definicion.get("processor"):
        # El cálculo de un procesador vive en el servidor y tiene sus pruebas
        # propias: aquí basta con que la definición sea la que él entiende.
        _definicion_procesador({**definicion, "id": "custom"})
    else:
        datos.validate_definition({**definicion, "id": "custom"})
        estudio.ejecutar_definicion(definicion, filas, parametros or {})
    ficha.definicion = definicion
    db.commit()
    db.refresh(ficha)
    return ficha


# --- E9: papel aprobado, versiones, contexto, encerar y eliminar -------------

# Tipos del papel aprobado que no son evidencia admitida (almacen.TIPOS decide qué sube el cliente).
_TIPO_PAPEL = {"pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation"}


def guardar_papel(db: Session, p: Prueba, revision: int, xlsx: bytes, html: bytes, actor: str,
                  docx: bytes | None = None, pptx: bytes | None = None) -> Prueba:
    """El papel aprobado se guarda una sola vez, con su huella, y ya no cambia.

    Lo arma el navegador con el exportador del sitio a partir del registro que
    el servidor ya aprobó (en Render no corre Node). En una prueba declarativa
    el navegador envía además el Word y el PowerPoint del papel (el HTML ya los
    lleva dentro); son opcionales para no romper clientes anteriores.
    """
    if revision != p.revision:
        raise Conflicto("La prueba cambió mientras la editaba. Actualice y vuelva a intentarlo.")
    if p.estado != "APROBADO":
        raise ReglaIncumplida("Solo una versión aprobada tiene papel final.")
    reg = copy.deepcopy(p.registro)
    if reg.get("artifacts"):
        raise ReglaIncumplida("El papel aprobado ya está guardado y no se reemplaza.")
    if not xlsx.startswith(b"PK") or not 0 < len(xlsx) <= almacen.MAX_ARCHIVO:
        raise ReglaIncumplida("El Excel del papel aprobado no es válido.")
    if b"<html" not in html[:2000].lower() or len(html) > almacen.MAX_ARCHIVO:
        raise ReglaIncumplida("El HTML del papel aprobado no es válido.")
    extra = [(ext, c) for ext, c in (("docx", docx), ("pptx", pptx)) if c is not None]
    for ext, contenido in extra:
        if not contenido.startswith(b"PK") or not 0 < len(contenido) <= almacen.MAX_ARCHIVO:
            raise ReglaIncumplida(f"El {'Word' if ext == 'docx' else 'PowerPoint'} del papel aprobado no es válido.")
    artefactos = {}
    for ext, contenido in (("xlsx", xlsx), ("html", html), *extra):
        huella = hashlib.sha256(contenido).hexdigest()
        nombre = f"Papel_aprobado_v{p.version}.{ext}"
        try:
            ruta = almacen.guardar(p.id, f"papel_v{p.version}_{huella[:16]}.{ext}", contenido)
        except almacen.SinEspacio as e:
            raise ReglaIncumplida(str(e))
        a = PruebaArchivo(prueba_id=p.id, requerimiento="PAPEL", nombre=nombre,
                          tipo=almacen.TIPOS.get(ext, _TIPO_PAPEL.get(ext, "text/html")), tamano=len(contenido), sha256=huella,
                          ruta=ruta, clase="workpaper", subido_por=actor)
        db.add(a)
        db.flush()
        artefactos[ext] = {"id": a.id, "hash": huella, "nombre": nombre}
    reg["artifacts"] = artefactos
    p.registro = reg
    p.revision += 1
    _evento(db, p, "workpaper", "APROBADO", actor, "Papel aprobado guardado con su huella.")
    db.commit()
    db.refresh(p)
    return p


def guardar_papel_declarativo(db: Session, p: Prueba, revision: int, carga: dict, actor: str) -> Prueba:
    """Papel aprobado de una prueba DECLARATIVA con el diseño de los procesadores.

    El navegador envía las cédulas con fórmulas del exportador del sitio (``cargaPapel``); el
    servidor arma aquí el Excel, el HTML, el Word y el PowerPoint (``procesadores.declarativo``)
    y los guarda con su huella. La definición, la versión y el estado salen de la prueba, no del
    navegador."""
    from backend.app.aud.niif.procesadores import declarativo

    if procesadores.de(p.definicion):
        raise ReglaIncumplida("El papel de una prueba con procesador lo arma el servidor al aprobarla.")
    # Las mismas reglas de guardar_papel, antes de armar nada.
    if revision != p.revision:
        raise Conflicto("La prueba cambió mientras la editaba. Actualice y vuelva a intentarlo.")
    if p.estado != "APROBADO":
        raise ReglaIncumplida("Solo una versión aprobada tiene papel final.")
    if (p.registro or {}).get("artifacts"):
        raise ReglaIncumplida("El papel aprobado ya está guardado y no se reemplaza.")
    if not isinstance(carga, dict) or not isinstance(carga.get("herramienta"), dict):
        raise ReglaIncumplida("Faltan las cédulas del papel.")
    carga = {**carga, "herramienta": {**carga["herramienta"], "definition": p.definicion, "version": p.version,
                                      "state": p.estado, "demo": False}}
    try:
        a = declarativo.papel(carga)
    except declarativo.CargaInvalida as e:
        raise ReglaIncumplida(str(e))
    return guardar_papel(db, p, revision, a["xlsx"], a["html"], actor, docx=a["docx"], pptx=a["pptx"])


MOTIVO_VERSION = "Indique el motivo de la nueva versión (NIA 230: qué cambia y por qué), con al menos 10 caracteres."
POSTERIOR_INFORME = "Cambio posterior a la fecha del informe (NIA 230 párr. 16)"


def nueva_version(db: Session, old: Prueba, revision: int, actor: str, motivo: str = "") -> Prueba:
    """Puerto de la acción ``new_version`` de route.ts. M1 (NIA 230): exige el motivo, que queda con su autor y fecha en la
    bitácora; si la fecha del informe ya pasó, la versión se marca como cambio posterior al informe."""
    if revision != old.revision:
        raise Conflicto("La prueba cambió mientras la editaba. Actualice y vuelva a intentarlo.")
    motivo = str(motivo or "").strip()[:2000]
    if len(motivo) < 10:
        raise ReglaIncumplida(MOTIVO_VERSION)
    if old.estado != "APROBADO":
        raise ReglaIncumplida("Solo una versión aprobada origina una nueva versión.")
    if db.execute(select(Prueba.id).where(Prueba.parent_id == old.id)).first():
        raise ReglaIncumplida("Esta versión ya tiene una versión sucesora. Abra la más reciente.")
    r = old.registro
    registro = {
        "methodologyVersion": VERSIONES["methodologyVersion"], "contextOverride": r.get("contextOverride") or False,
        "engagement": r["engagement"], "country": r["country"], "taxApplicable": r.get("taxApplicable", False),
        "taxScope": r.get("taxScope", ""), "program": [],
        "sources": [{**x, "verified": False} for x in r.get("sources") or []], "sourcesVerified": False,
        "requests": [], "rows": [], "parameters": r.get("parameters") or {}, "notes": [], "analysis": "",
        "conclusion": "", "conclusionReviewed": False, "createdAt": _ahora_iso(), "createdBy": actor,
    }
    fi = str((r.get("parameters") or {}).get("fechaInforme") or "")[:10]
    posterior = bool(fi) and _hoy().isoformat() > fi
    registro["versionMotivo"] = motivo
    registro["posteriorInforme"] = posterior
    p = Prueba(project_id=old.project_id, parent_id=old.id, version=old.version + 1, estado="PRUEBA_SELECCIONADA",
               origen=old.origen, definicion=old.definicion, registro=registro, revision=1, creada_por=actor)
    db.add(p)
    db.flush()
    _evento(db, p, "new_version", None, actor, f"Versión anterior: v{old.version} (prueba {old.id}). Motivo: {motivo}"
            + (f" · {POSTERIOR_INFORME}" if posterior else ""))
    db.commit()
    db.refresh(p)
    return p


# NIA 230: una versión aprobada es documentación del encargo. No se reinicia ni se elimina (con ella se irían el papel
# aprobado con su huella y la bitácora); si hay que corregirla, se crea una versión nueva que deja constancia.
APROBADA_NO_SE_TOCA = ("Esta versión está aprobada y es evidencia del encargo (NIA 230): no se reinicia ni se elimina. "
                       "Si hay que corregirla, cree una nueva versión.")
SIN_SEGREGACION = "Aprobado por quien lo envió a revisión: sin segregación de funciones (NIA 220)."


def _confirma_cliente(p: Prueba, datos: dict) -> bool:
    return str(datos.get("confirmClient") or "") == str(p.registro["engagement"].get("client") or "")


def encerar(db: Session, p: Prueba, revision: int, datos: dict, actor: str) -> Prueba:
    """Puerto de ``eraseTool``: borra evidencia, resultados e historial; la
    prueba queda en la lista, lista para empezar de nuevo."""
    if revision != p.revision:
        raise Conflicto("La prueba cambió mientras la editaba. Actualice y vuelva a intentarlo.")
    if p.estado == "APROBADO":
        raise ReglaIncumplida(APROBADA_NO_SE_TOCA)
    if not _confirma_cliente(p, datos) or datos.get("downloadConfirmed") is not True:
        raise ReglaIncumplida("Confirme el cliente y que conserva el archivo o acepta eliminar la prueba sin resultados.")
    r = p.registro
    anterior = p.estado
    p.registro = {
        "engagement": r["engagement"], "country": r["country"], "taxApplicable": r.get("taxApplicable", False),
        "taxScope": "", "sources": reglas.fuentes_oficiales(p.definicion, r["engagement"]["framework"], r["country"],
                                                             bool(r.get("taxApplicable"))),
        "sourcesVerified": False, "program": [], "requests": [], "rows": [], "run": None,
        "parameters": {"cutoff": r["engagement"]["cutoff"], "buckets": []}, "notes": [], "analysis": "",
        "conclusion": "", "conclusionReviewed": False, "evidenceStatus": {},
        "methodologyVersion": VERSIONES["methodologyVersion"], "contextOverride": r.get("contextOverride") or False,
        "createdAt": r.get("createdAt"), "createdBy": r.get("createdBy"), "erasedAt": _ahora_iso(),
    }
    p.estado = "PRUEBA_SELECCIONADA"
    for a in archivos(db, p.id):
        db.delete(a)
    for e in eventos(db, p.id):
        db.delete(e)
    p.revision += 1
    _evento(db, p, "erase", anterior, actor)
    db.commit()
    # Los archivos se borran del disco después de confirmar la base: si esto
    # fallara quedaría una carpeta huérfana, nunca una fila sin su archivo.
    almacen.borrar_prueba(p.id)
    db.refresh(p)
    return p


def eliminar(db: Session, p: Prueba, revision: int, datos: dict) -> dict:
    """Puerto de ``deleteTool``: quita la prueba con su evidencia e historial."""
    if revision != p.revision:
        raise Conflicto("La prueba cambió mientras la editaba. Actualice y vuelva a intentarlo.")
    if not _confirma_cliente(p, datos) or datos.get("deleteConfirmed") is not True:
        raise ReglaIncumplida("Escriba el nombre del cliente y confirme que la eliminación es definitiva.")
    if p.estado == "APROBADO":
        raise ReglaIncumplida(APROBADA_NO_SE_TOCA)
    if db.execute(select(Prueba.id).where(Prueba.parent_id == p.id)).first():
        raise Conflicto("Esta prueba tiene una versión sucesora. Elimine primero la más reciente.")
    salida = {"deleted": True, "id": p.id, "name": p.definicion.get("name") or "Prueba",
              "client": p.registro["engagement"].get("client") or ""}
    for a in archivos(db, p.id):
        db.delete(a)
    for e in eventos(db, p.id):
        db.delete(e)
    db.delete(p)
    db.commit()
    almacen.borrar_prueba(salida["id"])
    return salida


def editar_contexto(db: Session, old: Prueba, revision: int, datos: dict, actor: str) -> Prueba:
    """Puerto de ``editContext``: cambiar la ficha del encargo para esta prueba,
    para varias o para todas las abiertas del proyecto. Las afectadas vuelven a
    empezar: la ficha cambia fuentes, requerimientos y datos."""
    if revision != old.revision:
        raise Conflicto("La prueba cambió. Actualice antes de guardar.")
    if old.estado == "APROBADO":
        raise Conflicto("Esta versión está cerrada. Cree otra versión antes de editar.")
    ctx = reglas.validar_ficha_encargo(datos.get("context") or {}, completa=True)
    alcance = datos.get("scope")
    if alcance not in ("one", "selected", "all"):
        raise ReglaIncumplida("Seleccione el alcance del cambio.")
    ctx["reuseScope"] = alcance
    candidatas = list(db.execute(select(Prueba).where(Prueba.project_id == old.project_id)).scalars())
    elegidas = [old.id] if alcance == "one" else datos.get("toolIds") if alcance == "selected" else []
    if alcance == "selected" and (not isinstance(elegidas, list) or not elegidas or old.id not in elegidas):
        raise ReglaIncumplida("Seleccione esta prueba y las adicionales.")
    if any(i not in {c.id for c in candidatas} for i in elegidas):
        raise ReglaIncumplida("Solo se pueden seleccionar pruebas de este encargo.")
    objetivo = [c for c in candidatas
                if (not c.registro.get("contextOverride") or c.id == old.id if alcance == "all" else c.id in elegidas)
                and c.estado != "APROBADO"]
    if not any(c.id == old.id for c in objetivo) or len(objetivo) > 50:
        raise ReglaIncumplida("Seleccione entre 1 y 50 pruebas abiertas.")
    if alcance == "selected" and len(objetivo) != len(set(elegidas)):
        raise Conflicto("La selección incluye versiones cerradas.")
    if any(c.definicion.get("id") == "pce" and ctx["framework"] != "NIIF completas" for c in objetivo):
        raise ReglaIncumplida("Una prueba PCE seleccionada requiere NIIF completas; use un diseño específico para PYMES.")
    afectadas = ", ".join(str(c.id) for c in objetivo)
    for c in objetivo:
        reg = invalidar(copy.deepcopy(c.registro), "Cambió la ficha del encargo. Revise fuentes, requerimientos y datos.")
        reg.update(
            engagement={**reg["engagement"], **ctx}, country=ctx["country"], contextOverride=alcance != "all",
            methodologyVersion=VERSIONES["methodologyVersion"], parameters={"cutoff": ctx["cutoff"], "buckets": []},
            program=[], sources=reglas.fuentes_oficiales(c.definicion, ctx["framework"], ctx["country"],
                                                         bool(reg.get("taxApplicable"))),
            sourcesVerified=False, researchedAt=None, methodologyAgent=None, requests=[],
        )
        anterior = c.estado
        c.registro = reg
        c.estado = "PRUEBA_SELECCIONADA"
        c.revision += 1
        _evento(db, c, "edit_context", anterior, actor, f"Alcance {alcance}; pruebas afectadas: {afectadas}")
    if alcance == "all":
        f = db.get(FichaEncargo, old.project_id)
        if f is not None:
            f.datos = {**f.datos, **ctx}
            f.actualizada_por = actor
    db.commit()
    db.refresh(old)
    return old


# --- encargos NIIF, independientes del Workspace ------------------------------
# Un encargo es, por dentro, un proyecto AUD con su cliente y su ficha. Se crea
# desde la herramienta, en una sola transacción, sin pasar por Workspaces.

def listar_encargos(db: Session, user) -> list[dict]:
    from backend.app.context.models import Client, Project
    from backend.app.context.service import user_can_access_project

    if not user.organization_id:
        return []
    filas = db.execute(
        select(Project, Client).join(Client, Client.id == Project.client_id)
        .where(Project.organization_id == user.organization_id, Project.module_code == "AUD")
        .order_by(Client.name, Project.name)
    ).all()
    salida = []
    for pr, c in filas:
        if not user_can_access_project(db, user, pr):
            continue
        f = db.get(FichaEncargo, pr.id)
        n = db.execute(select(Prueba.id).where(Prueba.project_id == pr.id)).all()
        salida.append({
            "id": pr.id, "nombre": pr.name, "cliente": c.name, "client_id": c.id, "periodo": pr.period_label,
            "marco": (f.datos or {}).get("framework") if f else None,
            "corte": (f.datos or {}).get("cutoff") if f else None,
            "pruebas": len(n),
        })
    return salida


def crear_encargo(db: Session, user, datos: dict) -> dict:
    """Cliente (existente o nuevo), proyecto AUD y ficha del encargo, juntos."""
    from backend.app.context.models import Client, Project

    if not user.organization_id:
        raise ReglaIncumplida("Su usuario no tiene organización.")
    ficha = reglas.validar_ficha_encargo(datos.get("ficha") or {}, completa=True)
    client_id = datos.get("client_id")
    if client_id:
        cliente = db.get(Client, int(client_id)) if str(client_id).isdigit() else None
        if cliente is None or cliente.organization_id != user.organization_id:
            raise ReglaIncumplida("Cliente no encontrado.")
    else:
        nombre = str(datos.get("cliente") or ficha.get("client") or "").strip()[:200]
        if len(nombre) < 2:
            raise ReglaIncumplida("Indique el cliente.")
        cliente = db.execute(
            select(Client).where(Client.organization_id == user.organization_id,
                                 func.lower(Client.name) == nombre.lower())
        ).scalars().first()
        if cliente is None:
            cliente = Client(organization_id=user.organization_id, name=nombre,
                             tax_id=ficha.get("ruc") or None)
            db.add(cliente)
            db.flush()
    nombre_encargo = str(datos.get("nombre") or "").strip()[:200] or f"Auditoría {ficha['year']}"
    proyecto = Project(organization_id=user.organization_id, client_id=cliente.id, name=nombre_encargo,
                       module_code="AUD", period_label=f"AF {ficha['year']}")
    db.add(proyecto)
    db.flush()
    db.add(FichaEncargo(project_id=proyecto.id, datos=ficha, actualizada_por=user.email))
    db.commit()
    return {"id": proyecto.id, "nombre": proyecto.name, "cliente": cliente.name, "client_id": cliente.id,
            "periodo": proyecto.period_label, "marco": ficha["framework"], "corte": ficha["cutoff"], "pruebas": 0}


# --- registros del encargo con un clic (decisión del dueño, 2026-09-26) -------

TIPOS_REGISTRO = ("independencia", "asistencia", "aceptacion", "carta", "comunicacion", "indagacion", "consulta", "diferencia",
                  "enfoque")
# Varios registros vigentes a la vez: las indagaciones, las consultas y las diferencias de opinión no se reemplazan.
ACUMULAN = ("indagacion", "consulta", "diferencia")
CONSULTAS_BLOQUEAN = ("Hay consultas técnicas o diferencias de opinión abiertas en el registro del encargo: resuélvalas antes de "
                      "aprobar (NIA 220).")
# Un solo registro vigente por persona (independencia, asistencia) o por encargo (los demás): el nuevo anula al anterior.
POR_PERSONA = ("independencia", "asistencia")


def _roles() -> tuple:
    from backend.app.aud.niif.procesadores import planificacion_encargo as enc
    return enc.ROLES


def _hoy() -> datetime.date:
    return datetime.date.today()


def _fecha_registro(v, hoy: datetime.date) -> datetime.date:
    if v in (None, ""):
        return hoy
    try:
        f = datetime.date.fromisoformat(str(v)[:10])
    except ValueError:
        raise ReglaIncumplida("Fecha inválida (AAAA-MM-DD).")
    if f > hoy:
        raise ReglaIncumplida("La fecha no puede ser posterior a hoy.")
    return f


def _texto(v, n: int = 1000) -> str:
    return str(v or "").strip()[:n]


def _vigentes(db: Session, project_id: int) -> list[RegistroEncargo]:
    return list(db.execute(
        select(RegistroEncargo).where(RegistroEncargo.project_id == project_id, RegistroEncargo.anulado_en.is_(None))
        .order_by(RegistroEncargo.id)
    ).scalars())


def _anular(r: RegistroEncargo, actor: str) -> None:
    r.anulado_por = actor
    r.anulado_en = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


def anios_con_cliente(db: Session, project_id: int, actor: str, anio_desde: int | None) -> int:
    """Años del integrante con el cliente: encargos del mismo cliente en los que confirmó su independencia (este
    incluido) o, si lo declaró, los años desde que empezó a atenderlo; el mayor de los dos."""
    from backend.app.context.models import Project

    pr = db.get(Project, project_id)
    n = 1
    if pr is not None:
        ids = select(Project.id).where(Project.client_id == pr.client_id)
        otros = db.execute(
            select(func.count(func.distinct(RegistroEncargo.project_id))).where(
                RegistroEncargo.project_id.in_(ids), RegistroEncargo.project_id != project_id,
                RegistroEncargo.tipo == "independencia", RegistroEncargo.actor == actor,
                RegistroEncargo.anulado_en.is_(None))
        ).scalar() or 0
        n = 1 + int(otros)
    ficha = leer_ficha(db, project_id) or {}
    anio = int(ficha["year"]) if str(ficha.get("year") or "").isdigit() else _hoy().year
    if anio_desde:
        n = max(n, anio - int(anio_desde) + 1)
    return n


def registrar(db: Session, project_id: int, datos: dict, actor: str) -> RegistroEncargo:
    tipo = _texto(datos.get("tipo"), 20)
    if tipo not in TIPOS_REGISTRO:
        raise ReglaIncumplida("Tipo de registro desconocido.")
    hoy = _hoy()
    vig = _vigentes(db, project_id)
    # El nombre con que figura en el papel: el que escribió o el de su confirmación de independencia; si no, su correo.
    propio = [r.nombre for r in vig if r.tipo == "independencia" and r.actor == actor]
    nombre = _texto(datos.get("nombre"), 200) or (propio[-1] if propio else actor)
    extra: dict = {}
    rol = None
    fecha = hoy
    if tipo in POR_PERSONA:
        rol = _texto(datos.get("rol"), 40)
        if rol not in _roles():
            raise ReglaIncumplida("Indique su rol en el encargo.")
    if tipo == "independencia":
        extra = {"amenazas": _texto(datos.get("amenazas")), "salvaguardas": _texto(datos.get("salvaguardas"))}
        desde = str(datos.get("anio_desde") or "").strip()
        if desde:
            if not desde.isdigit() or not 1950 <= int(desde) <= hoy.year:
                raise ReglaIncumplida("Año desde el que atiende al cliente inválido.")
            extra["anio_desde"] = int(desde)
    elif tipo == "asistencia":
        fecha = _fecha_registro(datos.get("fecha"), hoy)
    elif tipo == "aceptacion":
        socio = [r for r in vig if r.tipo == "independencia" and r.actor == actor and r.rol == "Socio"]
        if not socio:
            raise ReglaIncumplida("La aceptación la registra el socio del encargo, después de confirmar su independencia como «Socio».")
        nombre = socio[-1].nombre
    elif tipo == "carta":
        fecha = _fecha_registro(datos.get("fecha"), hoy)
        extra = {"detalle": _texto(datos.get("limitaciones"))}
    elif tipo == "comunicacion":
        fecha = _fecha_registro(datos.get("fecha"), hoy)
        medio = _texto(datos.get("medio"), 200)
        if not medio:
            raise ReglaIncumplida("Indique el medio de la comunicación (reunión, correo, carta).")
        extra = {"detalle": medio}
    elif tipo == "indagacion":
        from backend.app.aud.niif.procesadores import planificacion_calidad as cal
        fecha = _fecha_registro(datos.get("fecha"), hoy)
        tema, proc = _texto(datos.get("tema"), 80), _texto(datos.get("procedimiento"), 40) or "Indagación"
        if tema not in cal.TEMAS:
            raise ReglaIncumplida("Elija el tema de la indagación.")
        if proc not in cal.PROCEDIMIENTOS:
            raise ReglaIncumplida("El procedimiento es indagación, observación o inspección.")
        resumen = _texto(datos.get("resumen"), 2000)
        if len(resumen) < 10:
            raise ReglaIncumplida("Resuma lo que se obtuvo de la indagación u observación.")
        extra = {"tema": tema, "procedimiento": proc, "persona": _texto(datos.get("persona"), 200), "resumen": resumen}
    elif tipo == "enfoque":
        # Todo ciclo es sustantivo por política de la firma (hoja 45); el socio puede registrar otra decisión por ciclo.
        from backend.app.aud.niif.procesadores import planificacion_enfoque as enf
        socio = [r for r in vig if r.tipo == "independencia" and r.actor == actor and r.rol == "Socio"]
        if not socio:
            raise ReglaIncumplida("El enfoque de cada ciclo lo confirma el socio del encargo, después de confirmar su independencia "
                                  "como «Socio».")
        nombre, rol = socio[-1].nombre, "Socio"
        ciclo, decision = _texto(datos.get("ciclo"), 80), _texto(datos.get("decision"), 40)
        if ciclo not in enf.NOMBRES_CICLO:
            raise ReglaIncumplida("Ciclo desconocido.")
        if decision not in enf.DECISIONES:
            raise ReglaIncumplida("El enfoque es «Confiar en controles» o «Sustantivo».")
        motivo = _texto(datos.get("motivo"), 1000)
        if len(motivo) < 10:
            raise ReglaIncumplida("Documente el motivo del enfoque (al menos 10 caracteres).")
        extra = {"ciclo": ciclo, "decision": decision, "motivo": motivo}
    elif tipo in ("consulta", "diferencia"):
        tema = _texto(datos.get("tema"), 300)
        if len(tema) < 5:
            raise ReglaIncumplida("Indique el tema de la consulta o de la diferencia de opinión.")
        extra = {"tema": tema, "detalle": _texto(datos.get("detalle")), "estado": "Abierta"}
    for r in vig:
        if tipo == "enfoque":
            if r.tipo == "enfoque" and (r.datos or {}).get("ciclo") == extra["ciclo"]:
                _anular(r, actor)
        elif tipo not in ACUMULAN and r.tipo == tipo and (tipo not in POR_PERSONA or r.actor == actor):
            _anular(r, actor)
    reg = RegistroEncargo(project_id=project_id, tipo=tipo, actor=actor, nombre=nombre, rol=rol, fecha=fecha, datos=extra)
    db.add(reg)
    db.commit()
    db.refresh(reg)
    return reg


def anular_registro(db: Session, project_id: int, registro_id: int, actor: str, es_admin: bool) -> None:
    r = db.get(RegistroEncargo, registro_id)
    if r is None or r.project_id != project_id or r.anulado_en is not None:
        raise ReglaIncumplida("Registro no encontrado.")
    if r.actor != actor and not es_admin:
        raise ReglaIncumplida("Solo quien hizo el registro (o un administrador) puede anularlo.")
    _anular(r, actor)
    db.commit()


def resolver_consulta(db: Session, project_id: int, registro_id: int, resolucion: str, actor: str) -> RegistroEncargo:
    """M3 (NIA 220): la consulta o la diferencia de opinión se cierra con su resolución, quién la resolvió y cuándo."""
    r = db.get(RegistroEncargo, registro_id)
    if r is None or r.project_id != project_id or r.anulado_en is not None or r.tipo not in ("consulta", "diferencia"):
        raise ReglaIncumplida("Consulta no encontrada.")
    if (r.datos or {}).get("estado") != "Abierta":
        raise ReglaIncumplida("La consulta ya está resuelta.")
    resolucion = _texto(resolucion, 2000)
    if len(resolucion) < 10:
        raise ReglaIncumplida("Documente la resolución (al menos 10 caracteres).")
    r.datos = {**(r.datos or {}), "estado": "Resuelta", "resolucion": resolucion, "resueltaPor": actor,
               "resueltaEn": _hoy().isoformat()}
    db.commit()
    db.refresh(r)
    return r


def consultas_abiertas(db: Session, project_id: int) -> int:
    return sum(1 for r in _vigentes(db, project_id) if r.tipo in ("consulta", "diferencia") and (r.datos or {}).get("estado") == "Abierta")


def version_anterior_run(db: Session, p: Prueba) -> dict | None:
    """Materialidad y riesgos de la versión anterior (hoja 13 guardada en su ejecución)."""
    old = db.get(Prueba, p.parent_id) if p.parent_id else None
    run = (old.registro or {}).get("run") if old else None
    if not run:
        return None
    h13 = next((h for h in run.get("hojas") or [] if str(h.get("name", "")).startswith("13_")), None)
    val = lambda c: c.get("v") if isinstance(c, dict) else c  # noqa: E731
    riesgos = [{"rubro": val(f[2]), "cond": val(f[3]), "presenta": val(f[5]), "riesgo": val(f[6]), "sev": val(f[7])}
               for f in (h13 or {}).get("rows") or []]
    return {"version": old.version, "fecha": (old.aprobada_en or old.actualizada_en).date().isoformat() if (old.aprobada_en or old.actualizada_en) else "",
            "totales": {k: (run.get("totals") or {}).get(k) for k in ("materialidad", "desempeno", "trivial")}, "riesgos": riesgos}


def resultado_para_revision(db: Session, p: Prueba) -> dict:
    """Re-ejecuta el procesador de la prueba para obtener su resultado COMPLETO.

    La consola de revisión del auditor recalcula sobre ``detalle`` (est9, cuentas,
    índices), pero el ``run`` guardado en la prueba recorta ``detalle`` a
    ``tasas/fiscal/cortes`` para no inflar la base. Aquí se vuelve a ejecutar el
    procesador con los mismos insumos y parámetros que ``aplicar_accion`` usa en
    ``execute`` (mismo marco, edición, registros del encargo, versión anterior y
    audit trail), de modo que la consola revise exactamente lo que se ejecutó, con
    el detalle íntegro. Es de solo lectura: no toca la prueba ni el estado.
    """
    proc = procesadores.de(p.definicion)
    if proc is None:
        raise ReglaIncumplida("Esta prueba no tiene procesador; no hay recálculo que revisar.")
    reg = p.registro or {}
    if not reg.get("engagement") or not reg["engagement"].get("cutoff"):
        raise ReglaIncumplida("Falta la ficha del encargo (fecha de corte) para recalcular.")
    param = {k: v for k, v in (reg.get("parameters") or {}).items() if k in proc.PARAMETROS}
    param["_marco"] = reg["engagement"].get("framework") or ""
    param["_edicion"] = str(reg["engagement"].get("edition") or "")
    if getattr(proc, "USA_REGISTROS_ENCARGO", False):
        param["_encargo"] = registros_encargo(db, p.project_id)
        anterior = version_anterior_run(db, p)
        if anterior:
            param["_anterior"] = anterior
        param["_archivos"] = archivos_de_entrada(db, p.id)
    try:
        return proc.ejecutar(reg.get("datasets") or {}, param, reg["engagement"]["cutoff"])
    except (ValueError, KeyError, ArithmeticError, StopIteration) as e:
        raise ReglaIncumplida(str(e) or "La prueba no se pudo recalcular para la revisión.")


def guion_consola_chat(db: Session, p: Prueba, rol: str) -> dict:
    """Guion de la consola-chat de la prueba (agente determinista, solo lectura).

    Vale para la planificación NIA y para las 20 herramientas del catálogo: toda
    prueba con procesador tiene el mismo ciclo (documentos → producir → enviar →
    revisar → aprobar) y, por tanto, el mismo hilo conversacional.
    """
    from backend.app.aud.niif.ciclo import consola_chat

    if not (p.definicion or {}).get("processor"):
        raise ReglaIncumplida("Esta prueba no tiene procesador; la consola-chat requiere una herramienta del catálogo.")
    es_plan = (p.definicion or {}).get("processor") == "planificacion_nia"
    reg = p.registro or {}
    reqs = reg.get("requests") or []
    fuentes = [a for a in archivos(db, p.id) if a.clase == "source"]
    docs = [{"id": a.id, "requestId": a.requerimiento, "component": a.componente} for a in fuentes]
    rechazados = [a.id for a in fuentes if a.estado == "rechazado"]
    cobertura = datos.tool_coverage(reqs, docs, rechazados) if reqs else []
    huecos = datos.tool_gaps(reqs, docs, rechazados) if reqs else []
    obligatorios = [c for c in cobertura if c.get("required")]
    pendientes = [c["text"] for c in obligatorios if not c.get("complete")]
    # Antes de generar el requerimiento todavía no hay `requests`: los documentos que pedirá salen de la definición.
    if not reqs:
        pendientes = [r.get("document") or r.get("id") for r in (p.definicion.get("requests") or []) if r.get("required") is not False]
    d = {
        "estado": p.estado,
        "cliente": (reg.get("engagement") or {}).get("client"),
        "prueba": (p.definicion or {}).get("name") or "la prueba",
        "es_planificacion": es_plan,
        "huecos": huecos,
        "pendientes": pendientes,
        "recibidos": sum(1 for c in obligatorios if c.get("complete")),
        "total": len(obligatorios),
        "tiene_run": bool(reg.get("run")),
        "conclusion_hecha": bool(str(reg.get("conclusion") or "").strip()),
        "aprobada_por": reg.get("approvedBy"),
    }
    # En revisión y del lado del auditor, el agente ya trae el veredicto del recálculo independiente.
    if p.estado == "EN_REVISION" and rol == "auditor" and reg.get("run"):
        try:
            rep = revisar_prueba(db, p)
            d.update(veredicto=rep["veredicto"], bloqueos=rep.get("bloqueos") or [], hallazgos=rep.get("hallazgos") or [])
        except ReglaIncumplida:
            pass
    return {"prueba_id": p.id, "estado": p.estado, "version": p.version, "revision": p.revision,
            **consola_chat.guion(d, rol)}


def revisar_prueba(db: Session, p: Prueba) -> dict:
    """Reporte de la consola de revisión del auditor para una prueba con procesador.

    Despacha según la herramienta: la planificación NIA usa su revisor rico
    (``consola_revision``, que recalcula índices y agregados); las 20 herramientas
    del catálogo usan el revisor genérico por contrato (``revision.base``), que
    verifica el panel, el enlace de los problemas y el recálculo independiente del
    resultado principal a medida por rubro (``revision/recalc/<processor>.py``).
    """
    processor = (p.definicion or {}).get("processor")
    if not processor:
        raise ReglaIncumplida("Esta prueba no tiene procesador; no hay recálculo que revisar.")
    if not (p.registro or {}).get("run"):
        raise ReglaIncumplida("Procese la prueba antes de revisarla.")
    run = resultado_para_revision(db, p)
    if processor == "planificacion_nia":
        from backend.app.aud.niif.ciclo import consola_revision
        return consola_revision.revisar(run)
    from backend.app.aud.niif.ciclo import revision
    return revision.revisar(run, procesadores.de(p.definicion), processor)


# Alias retrocompatible: el nombre anterior era exclusivo de la planificación.
def revisar_planificacion(db: Session, p: Prueba) -> dict:
    return revisar_prueba(db, p)


def registro_salida(r: RegistroEncargo) -> dict:
    return {"id": r.id, "tipo": r.tipo, "actor": r.actor, "nombre": r.nombre, "rol": r.rol,
            "fecha": r.fecha.isoformat(), "datos": r.datos or {},
            "creado_en": r.creado_en.isoformat() if r.creado_en else None}


def registros_encargo(db: Session, project_id: int) -> dict:
    """Lo que la planificación recibe en ``parametros["_encargo"]`` (planificacion_encargo.registros)."""
    vig = _vigentes(db, project_id)
    equipo, asistencia, indagaciones, consultas, enfoque, uno = [], [], [], [], [], {}
    for r in vig:
        d = r.datos or {}
        if r.tipo == "independencia":
            equipo.append({"integrante": r.nombre, "rol": r.rol, "fecha": r.fecha.isoformat(), "amenazas": d.get("amenazas", ""),
                           "salvaguardas": d.get("salvaguardas", ""),
                           "anios": anios_con_cliente(db, project_id, r.actor, d.get("anio_desde"))})
        elif r.tipo == "asistencia":
            asistencia.append({"integrante": r.nombre, "rol": r.rol, "fecha": r.fecha.isoformat()})
        elif r.tipo == "indagacion":
            indagaciones.append({"actor": r.nombre, "fecha": r.fecha.isoformat(), **{k: d.get(k, "") for k in
                                                                                    ("tema", "procedimiento", "persona", "resumen")}})
        elif r.tipo == "enfoque":
            enfoque.append({"ciclo": d.get("ciclo", ""), "decision": d.get("decision", ""), "actor": r.nombre,
                            "fecha": r.fecha.isoformat(), "motivo": d.get("motivo", "")})
        elif r.tipo in ("consulta", "diferencia"):
            consultas.append({"actor": r.nombre, "fecha": r.fecha.isoformat(), "tipo": r.tipo, "tema": d.get("tema", ""),
                              "estado": d.get("estado", "Abierta"),
                              "detalle": " · ".join(v for v in (d.get("detalle"), d.get("resolucion")) if v)})
        else:
            uno[r.tipo] = {"actor": r.nombre, "fecha": r.fecha.isoformat(), "detalle": d.get("detalle", "")}
    ficha = leer_ficha(db, project_id) or {}
    return {"registros": {"equipo": equipo, "asistencia": asistencia, "indagaciones": indagaciones, "consultas": consultas,
                          "enfoque": enfoque, **uno},
            "firma": ficha.get("firm") or "",
            "ficha": {k: ficha.get(k) for k in ("client", "ruc", "activity", "year", "cutoff", "framework", "edition")}}


def ultima_planificacion(db: Session, project_id: int) -> dict | None:
    """La ejecución más reciente de la planificación del encargo (fuente del acta y de la carta de planificación)."""
    for p in db.execute(select(Prueba).where(Prueba.project_id == project_id).order_by(Prueba.id.desc())).scalars():
        if (p.definicion or {}).get("processor") == "planificacion_nia" and (p.registro or {}).get("run"):
            return p.registro["run"]
    return None


def documento_encargo(db: Session, project_id: int, tipo: str) -> bytes:
    from backend.app.aud.niif.ciclo import documentos_encargo as docs

    if tipo not in docs.TIPOS:
        raise ReglaIncumplida("Documento desconocido.")
    ficha = leer_ficha(db, project_id)
    if not ficha:
        raise ReglaIncumplida("Complete primero la ficha del encargo.")
    return docs.generar(tipo, ficha, registros_encargo(db, project_id), ultima_planificacion(db, project_id))
