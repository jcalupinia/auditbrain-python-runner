# -*- coding: utf-8 -*-
"""Validación de formato de los documentos de la prueba de nómina.

Objetivo (decisión del dueño, 2026-10-29): que la herramienta NO se quede «pensando»
ni reviente con mensajes crípticos («Worksheet normal does not exist»). Antes de correr
el motor —o cuando el auditor lo pida— se valida CADA documento y se devuelve un
diagnóstico claro y accionable: qué documento, qué cabecera/columna falta y qué se
encontró, para que el auditor corrija el archivo o lo suba en el formato correcto.

No calcula nada ni toca datos del cliente fuera de la lectura de cabeceras; es solo
lectura. Los `problemas` son bloqueantes (sin ellos el motor no puede procesar); las
`advertencias` no bloquean pero avisan (p. ej. beneficios que saldrían en cero).
"""
from __future__ import annotations

import os

import openpyxl

from backend.app.aud.niif.procesadores.nomina import mayores, motor
from backend.app.aud.niif.procesadores.nomina import perfil_cuentas as pc

# Requerimientos mínimos para procesar y su nombre legible.
DOCS = {
    "RQ-002": "Anexo de nómina",
    "RQ-003": "Consolidado del IESS",
    "RQ-004": "Mayor(es) de nómina",
    "RQ-006": "Rol de pagos",
}

# Nombre legible de cada campo clave del rol (para el mensaje al auditor).
_ETIQUETA_ROL = {
    "nombre": "empleado (Nombre / Nombres / Apellidos y Nombres)",
    "sueldo": "Sueldo",
    "fr_rol": "Fondos de Reserva (del rol)",
    "d13mens": "Décimo Tercero (del rol)",
    "d14mens": "Décimo Cuarto (del rol)",
    "prov_d13": "Provisión Décimo Tercero",
    "prov_d14": "Provisión Décimo Cuarto",
    "prov_vac": "Provisión Vacaciones",
    "prov_fr": "Provisión Fondos de Reserva",
}


def _base(requerimiento: str, nombre: str) -> dict:
    return {"requerimiento": requerimiento, "documento": DOCS.get(requerimiento, requerimiento),
            "archivo": nombre, "ok": True, "problemas": [], "advertencias": [], "detalle": {}}


def _cabeceras(filas, hi: int) -> list:
    if hi is None or hi >= len(filas):
        return []
    return [str(c).strip() for c in (filas[hi] or []) if c not in (None, "")]


def validar_rol(ruta: str, nombre: str) -> dict:
    r = _base("RQ-006", nombre)
    try:
        hojas = openpyxl.load_workbook(ruta, read_only=True).sheetnames
    except Exception as e:
        r["ok"] = False
        r["problemas"].append(f"No pude abrir el archivo del rol de pagos: {e}")
        return r
    r["detalle"]["hojas"] = hojas
    if "normal" in hojas:
        # Rol ya en el layout del motor (hoja «normal», posicional desde la fila 6).
        try:
            regs = motor.leer_rol_normal(ruta)
        except Exception as e:
            r["ok"] = False
            r["problemas"].append(f"La hoja «normal» del rol no se pudo leer: {e}")
            return r
        if not regs:
            r["ok"] = False
            r["problemas"].append("La hoja «normal» del rol no tiene filas de empleados "
                                  "(se leen desde la fila 6). Verifique que el rol tenga datos.")
        else:
            r["detalle"]["empleados_mes"] = len(regs)
        return r
    # Rol en otra estructura: se intenta mapear por nombre de columna.
    try:
        ws = openpyxl.load_workbook(ruta, read_only=True, data_only=True).active
        filas = list(ws.iter_rows(values_only=True))
        hi, campos, _ = pc._mapa_rol(filas)
    except Exception as e:
        r["ok"] = False
        r["problemas"].append(f"No pude interpretar el rol de pagos: {e}")
        return r
    r["detalle"]["fila_encabezados"] = hi + 1  # 1-based para el auditor
    r["detalle"]["cabeceras_detectadas"] = _cabeceras(filas, hi)
    if campos.get("nombre") is None or campos.get("sueldo") is None:
        r["ok"] = False
        faltan = [_ETIQUETA_ROL[c] for c in ("nombre", "sueldo") if campos.get(c) is None]
        r["problemas"].append(
            "En el rol de pagos no encuentro la(s) columna(s) de: " + "; ".join(faltan) + ". "
            "El rol debe traer al menos una columna de empleado (Nombre/Nombres/Cédula) y una de "
            "Sueldo. Cabeceras detectadas en la fila "
            f"{hi + 1}: {', '.join(r['detalle']['cabeceras_detectadas']) or '(ninguna)'}."
        )
        return r
    faltan_benef = [c for c in ("fr_rol", "d13mens", "d14mens", "prov_d13", "prov_d14",
                                "prov_vac", "prov_fr") if campos.get(c) is None]
    if faltan_benef:
        r["advertencias"].append(
            "No reconocí columnas de: " + "; ".join(_ETIQUETA_ROL[c] for c in faltan_benef) + ". "
            "Esos beneficios saldrán en cero hasta que el rol los traiga con un nombre reconocible "
            "o se calibre el formato de este cliente.")
    return r


def validar_mayor(ruta: str, nombre: str) -> dict:
    r = _base("RQ-004", nombre)
    try:
        df = mayores._read_tabla(ruta)   # lanza ValueError descriptivo si falta una columna esencial
    except ValueError as e:
        r["ok"] = False
        r["problemas"].append(str(e))
        return r
    except Exception as e:
        r["ok"] = False
        r["problemas"].append(f"No pude leer el mayor «{nombre}»: {e}")
        return r
    r["detalle"]["filas"] = int(len(df))
    return r


def validar_consolidado(ruta: str, nombre: str) -> dict:
    r = _base("RQ-003", nombre)
    p = ruta
    try:
        if ruta.lower().endswith(".xls"):   # el motor lo convierte a .xlsx antes de leerlo
            from backend.app.aud.niif.procesadores.nomina_beneficios import _a_xlsx
            p = _a_xlsx(ruta, os.path.dirname(ruta) or ".")
        hojas = openpyxl.load_workbook(p, read_only=True).sheetnames
    except Exception as e:
        r["ok"] = False
        r["problemas"].append(f"No pude abrir el Consolidado del IESS: {e}")
        return r
    r["detalle"]["hojas"] = hojas
    # El motor acepta el export estándar del IESS en una sola hoja y lo adapta a la hoja
    # «detallePlanillaConsolidado». La validación replica esa adaptación para no bloquear un
    # consolidado que el motor SÍ procesa.
    destino, adaptado = p, False
    if "detallePlanillaConsolidado" not in hojas:
        try:
            destino = pc.reescribir_consolidado(p, p + ".cons_adaptado.xlsx")
            adaptado = True
        except Exception as e:
            r["ok"] = False
            r["problemas"].append(
                "El Consolidado del IESS no tiene la hoja «detallePlanillaConsolidado» ni un "
                "formato adaptable (export del IESS con columnas de Cédula y Período). "
                f"Hojas encontradas: {', '.join(hojas)}. Detalle: {e}")
            return r
    try:
        filas = motor.leer_consolidado(destino)
    except Exception as e:
        r["ok"] = False
        r["problemas"].append(f"No pude leer el Consolidado del IESS tras adaptarlo: {e}")
        return r
    if not filas:
        r["ok"] = False
        r["problemas"].append(
            "El Consolidado del IESS no tiene filas de aportes reconocibles (se esperan Cédula, "
            "Período y valores de aporte por empleado). Verifique que sea el export del IESS.")
    else:
        r["detalle"]["registros"] = len(filas)
        if adaptado:
            r["advertencias"].append("Se adaptó automáticamente del export estándar del IESS.")
    return r


def validar_anexo(ruta: str, nombre: str) -> dict:
    r = _base("RQ-002", nombre)
    try:
        ws = openpyxl.load_workbook(ruta, read_only=True, data_only=True).active
        cuentas = 0
        for row in ws.iter_rows(min_row=3, max_row=400, values_only=True):
            cod = row[0] if row else None
            if cod is not None and str(cod).strip()[:1].isdigit():
                cuentas += 1
        r["detalle"]["cuentas_detectadas"] = cuentas
        if cuentas == 0:
            r["ok"] = False
            r["problemas"].append(
                "El Anexo de nómina no tiene cuentas reconocibles en la columna A "
                "(desde la fila 3). Debe listar las cuentas con su código, descripción y saldos.")
    except Exception as e:
        r["ok"] = False
        r["problemas"].append(f"No pude leer el Anexo de nómina: {e}")
    return r


_VALIDADORES = {"RQ-002": validar_anexo, "RQ-003": validar_consolidado,
                "RQ-004": validar_mayor, "RQ-006": validar_rol}


def validar_documento(requerimiento: str, ruta: str, nombre: str, componente: str = "") -> dict:
    """Valida UN documento según su requerimiento. Nunca lanza: devuelve el diagnóstico."""
    rq = (requerimiento or "").upper()
    # Las exclusiones (RQ-003) son opcionales y tienen otra estructura: no se validan como consolidado.
    if rq == "RQ-003" and ("exclusi" in (componente or "").lower() or "exclusi" in (nombre or "").lower()):
        d = _base(rq, nombre)
        d["documento"] = "Exclusiones (opcional)"
        return d
    fn = _VALIDADORES.get(rq)
    if fn is None:
        d = _base(rq, nombre)
        d["documento"] = DOCS.get(rq, rq or "Documento")
        return d
    try:
        return fn(ruta, nombre)
    except Exception as e:   # el validador nunca debe reventar
        d = _base(rq, nombre)
        d["ok"] = False
        d["problemas"].append(f"No pude validar el documento: {e}")
        return d


def validar_prueba(archivos: list[dict]) -> dict:
    """Valida todos los documentos de la prueba y consolida el diagnóstico.

    ``archivos``: lista de dicts con ``requerimiento``, ``ruta``, ``nombre`` (``componente`` opcional).
    Devuelve ``{ok, bloqueante, faltan_requerimientos, documentos: [...], resumen: str}``.
    """
    documentos, presentes = [], set()
    for a in archivos or []:
        rq = (a.get("requerimiento") or "").upper()
        ruta = a.get("ruta") or ""
        if not ruta:
            continue
        presentes.add(rq)
        if rq in _VALIDADORES:
            documentos.append(validar_documento(rq, ruta, a.get("nombre") or os.path.basename(ruta),
                                                 a.get("componente") or ""))
    faltan = [f"{rq} · {DOCS[rq]}" for rq in ("RQ-002", "RQ-003", "RQ-004", "RQ-006") if rq not in presentes]
    con_problema = [d for d in documentos if d["problemas"]]
    bloqueante = bool(faltan or con_problema)
    lineas = []
    for rq in faltan:
        lineas.append(f"Falta subir: {rq}.")
    for d in con_problema:
        for p in d["problemas"]:
            lineas.append(f"{d['documento']} («{d['archivo']}»): {p}")
    return {
        "ok": not bloqueante,
        "bloqueante": bloqueante,
        "faltan_requerimientos": faltan,
        "documentos": documentos,
        "resumen": ("Todos los documentos están en el formato esperado."
                    if not bloqueante else "Hay documentos que impiden procesar:\n- " + "\n- ".join(lineas)),
    }
