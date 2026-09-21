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
from backend.app.aud.niif.ciclo.models import FichaEncargo, Prueba, PruebaArchivo, PruebaEvento
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
    return d


def _num_seguro(v) -> float:
    n = procesadores.perdidas_incurridas_s11.a_num(v)
    return n or 0.0


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
            if not conjuntos.get("a3"):
                raise ReglaIncumplida("Suba el anexo de cartera del ejercicio corriente antes de procesar.")
            filas_ds, mapeos, errores, avisos = {}, [], [], []
            for ds, partes in conjuntos.items():
                if ds not in por_ds or not isinstance(partes, list) or len(partes) > 60:
                    raise ReglaIncumplida("Anexo no previsto en los requerimientos de la ficha.")
                campos = proc.CAMPOS[proc.kind(ds)]
                filas_ds[ds] = []
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
                if sum(len(x) for x in filas_ds.values()) > datos_mod.MAX_ROWS:
                    raise ReglaIncumplida(f"Cargue entre 1 y {datos_mod.MAX_ROWS} registros.")
                v = proc.validar_filas(proc.kind(ds), filas_ds[ds])
                errores += [{**e, "message": f"{por_ds[ds]['id']} · {e['message']}"} for e in v["errors"]]
                avisos += [{**w, "message": f"{por_ds[ds]['id']} · {w['message']}"} for w in v["warnings"]]
            reg["datasets"] = filas_ds
            reg["rows"] = filas_ds["a3"]
            reg["mapping"] = mapeos[0]
            reg["mappings"] = mapeos
            reg["validation"] = {"records": len(filas_ds["a3"]), "errors": errores, "warnings": avisos, "ok": not errores}
            p.estado = "DOCUMENTACION_RECIBIDA"
            reg["run"] = None
            if not errores:
                reg["controlTotal"] = procesadores.perdidas_incurridas_s11.r2(sum(_num_seguro(f.get("saldo")) for f in filas_ds["a3"]))
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
            elif v is not None and str(v).strip() != "":
                n = proc.a_num(v)
                if n is None or n < 0:
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
                run = proc.ejecutar(reg.get("datasets") or {}, param, reg["engagement"]["cutoff"])
                run["hojas"] = proc.hojas(run)
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
        p.estado = reglas.transicion({**reg, "state": p.estado, "definition": p.definicion}, accion)
        reg["approvedBy"] = actor
        reg["approvedAt"] = _ahora_iso()
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

def guardar_papel(db: Session, p: Prueba, revision: int, xlsx: bytes, html: bytes, actor: str) -> Prueba:
    """El papel aprobado se guarda una sola vez, con su huella, y ya no cambia.

    Lo arma el navegador con el exportador del sitio a partir del registro que
    el servidor ya aprobó (en Render no corre Node).
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
    artefactos = {}
    for ext, contenido in (("xlsx", xlsx), ("html", html)):
        huella = hashlib.sha256(contenido).hexdigest()
        nombre = f"Papel_aprobado_v{p.version}.{ext}"
        try:
            ruta = almacen.guardar(p.id, f"papel_v{p.version}_{huella[:16]}.{ext}", contenido)
        except almacen.SinEspacio as e:
            raise ReglaIncumplida(str(e))
        a = PruebaArchivo(prueba_id=p.id, requerimiento="PAPEL", nombre=nombre,
                          tipo=almacen.TIPOS.get(ext, "text/html"), tamano=len(contenido), sha256=huella,
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


def nueva_version(db: Session, old: Prueba, revision: int, actor: str) -> Prueba:
    """Puerto de la acción ``new_version`` de route.ts."""
    if revision != old.revision:
        raise Conflicto("La prueba cambió mientras la editaba. Actualice y vuelva a intentarlo.")
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
    p = Prueba(project_id=old.project_id, parent_id=old.id, version=old.version + 1, estado="PRUEBA_SELECCIONADA",
               origen=old.origen, definicion=old.definicion, registro=registro, revision=1, creada_por=actor)
    db.add(p)
    db.flush()
    _evento(db, p, "new_version", None, actor, f"Versión anterior: v{old.version} (prueba {old.id})")
    db.commit()
    db.refresh(p)
    return p


def _confirma_cliente(p: Prueba, datos: dict) -> bool:
    return str(datos.get("confirmClient") or "") == str(p.registro["engagement"].get("client") or "")


def encerar(db: Session, p: Prueba, revision: int, datos: dict, actor: str) -> Prueba:
    """Puerto de ``eraseTool``: borra evidencia, resultados e historial; la
    prueba queda en la lista, lista para empezar de nuevo."""
    if revision != p.revision:
        raise Conflicto("La prueba cambió mientras la editaba. Actualice y vuelva a intentarlo.")
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
    if p.estado == "APROBADO" and datos.get("approvedConfirmed") is not True:
        raise ReglaIncumplida("Esta versión está aprobada y es evidencia del encargo. Confírmelo expresamente para eliminarla.")
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
