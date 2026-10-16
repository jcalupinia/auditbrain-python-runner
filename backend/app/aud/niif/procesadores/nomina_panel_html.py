# -*- coding: utf-8 -*-
"""Render del panel propio de la herramienta de nómina 2.0 (la «cara»).

Igual que ``artefacto_html`` hace con la planificación: toma la plantilla del panel
entregado por la firma (``assets/nomina_panel.tmpl.html``) y le inyecta el encargo del
Command Center (cliente, RUC, ejercicio, corte, visita, marco, preparado/revisado y el
logo del cliente) en el placeholder ``__NOMINA_ENC__``, más ``__NOMINA_API__`` con la
base del API y el id de la prueba para que los botones de descarga pidan las cédulas al
MOTOR Python. El motor y las 15 cédulas los produce ``nomina_beneficios.correr_prueba``;
esto solo arma el HTML del panel.
"""
from __future__ import annotations

import html as _html
import json
import os
import re

_TMPL = os.path.join(os.path.dirname(__file__), "..", "assets", "nomina_panel.tmpl.html")

# CSS extra del modo EMBEBIDO: el panel va DENTRO del Command Center (en un <iframe>), no en
# pestaña suelta. El menú lateral (.side) ya viene oculto en la plantilla; aquí se oculta además
# la barra superior propia del panel (.tb, el «crumb») porque el Command Center ya pone su
# cabecera, y se suelta el ancho máximo para que ocupe todo el iframe. Así no se duplica el chrome.
_EMBED_CSS = '<style>.tb{display:none!important}.pg{max-width:none}</style>'

# Firmas que la plantilla reconoce (constante FIRMS del panel): la del encargo decide cuál.
_FIRMAS = ("partner", "audit")


def _firma(engagement: dict) -> str:
    """'audit' (AuditConsulting, por defecto) o 'partner' (Partner Auditing) según la ficha."""
    f = str(engagement.get("firm") or engagement.get("firma") or "").strip().lower()
    if "partner" in f:
        return "partner"
    return "audit"


def _corte_ddmmyyyy(engagement: dict) -> str:
    """Corte en dd/mm/aaaa para el panel; acepta 'AAAA-MM-DD' o ya formateado."""
    raw = str(engagement.get("cutoff") or engagement.get("corte") or "").strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if m:
        return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
    return raw


def construir_encargo(engagement: dict) -> dict:
    """Objeto ``ENC`` del panel desde el encargo del Command Center (``reg['engagement']``)."""
    e = engagement or {}
    marco = str(e.get("framework") or e.get("marco") or "NIIF para las PYMES").strip()
    enc = {
        "cliente": str(e.get("client") or e.get("cliente") or ""),
        "ruc": str(e.get("ruc") or ""),
        "actividad": str(e.get("activity") or e.get("actividad") or ""),
        "ejercicio": str(e.get("year") or e.get("ejercicio") or ""),
        "corte": _corte_ddmmyyyy(e),
        "visita": str(e.get("visit") or e.get("visita") or "Preliminar"),
        "preparado": str(e.get("preparer") or e.get("preparado") or ""),
        "revisado": str(e.get("reviewer") or e.get("revisado") or ""),
        "firma": _firma(e),
        "marco": marco,
        "edicion": str(e.get("edition") or e.get("edicion") or ""),
        "pais": str(e.get("country") or e.get("pais") or "Ecuador"),
        "moneda": str(e.get("currency") or e.get("moneda") or "USD"),
    }
    logo = str(e.get("logoCliente") or e.get("clienteLogo") or "").strip()
    if logo:
        enc["clienteLogo"] = logo
    return enc


def marca_panel(engagement: dict) -> dict:
    """Logos de la cabecera (los mismos de ``marca.py`` que usa la planificación)."""
    from backend.app.aud.niif.procesadores import marca
    return {"audit": marca.data_uri("auditconsulting_blanco"),
            "auditOscuro": marca.data_uri("auditconsulting_oscuro"),
            "partner": marca.data_uri("partner_auditing"),
            "auditia": marca.data_uri("audit_ia")}


def _prog_vacio() -> dict:
    """Estructura vacía de ``PROG`` para una prueba sin procesar: las ventanas Programa,
    Hallazgos y Ajustes muestran «PENDIENTE DE PROCESAR» (lógica del panel), igual que el
    visor cuando no hay cédulas."""
    return {"prog": [], "rq": [], "norm": [], "hall": [], "h12": [], "aj": [], "efe": [], "xlsx": ""}


def construir_prog(extras: dict | None) -> dict:
    """Objeto ``PROG`` del panel desde los JSON del motor (``prog.json`` + ``do12.json``).

    ``prog.json`` (``mk_pa``): ``{prog, rq, norm, hall, xlsx}``. ``do12.json`` (``mk_do12``):
    ``{hall, aj, efe}``. El panel consume los hallazgos de DO-12 como ``PROG.h12`` y el
    programa DO-0 como ``PROG.prog``. Sin extras (prueba no procesada) → estructura vacía."""
    extras = extras or {}
    prog = extras.get("prog") or {}
    do12 = extras.get("do12") or {}
    if not prog:
        return _prog_vacio()
    return {
        "prog": prog.get("prog", []),
        "rq": prog.get("rq", []),
        "norm": prog.get("norm", []),
        "hall": prog.get("hall", []),
        "h12": do12.get("hall", []),
        "aj": do12.get("aj", []),
        "efe": do12.get("efe", []),
        "xlsx": prog.get("xlsx", ""),
    }


def _buscar_cedula(carpeta: str, prefijo: str) -> str | None:
    for nombre in sorted(os.listdir(carpeta)):
        if nombre.startswith(prefijo) and nombre.endswith(".xlsx"):
            return os.path.join(carpeta, nombre)
    return None


def construir_mdl(carpeta_cedulas: str | None) -> dict:
    """Objeto ``MDL`` del panel desde los datos del motor para la ventana de Vacaciones (DO-4V).

    ``MDL.vacx``: el bloque RESUMEN de la cédula VAC (liquidación hipotética) con sus valores
    YA RECALCULADOS y el estado de la prueba. ``MDL.k08``: el kárdex RQ-008 (número de filas).
    Sin carpeta de cédulas (prueba no procesada) → ``{}``: la ventana muestra «PENDIENTE DE
    PROCESAR». Nunca lanza: si una cédula falta o no se puede leer, esa clave queda fuera."""
    if not (carpeta_cedulas and os.path.isdir(carpeta_cedulas)):
        return {}
    import openpyxl

    from backend.app.aud.niif.procesadores.nomina import visor

    mdl: dict = {}
    vac = _buscar_cedula(carpeta_cedulas, "VAC_")
    if vac:
        try:
            wf = openpyxl.load_workbook(vac)
            wv = openpyxl.load_workbook(vac, data_only=True)
            if "VAC Calculadora" in wf.sheetnames:
                sf, sv = wf["VAC Calculadora"], wv["VAC Calculadora"]
                resumen, estado = [], ""
                # RESUMEN: etiqueta en A (merged), valor recalculado en E, filas 9..20.
                for r in range(9, 21):
                    etiqueta = sf.cell(r, 1).value
                    valor = sv.cell(r, 5).value
                    if etiqueta is None:
                        continue
                    if r == 20:  # «Estado de la prueba»
                        estado = str(valor or "").strip()
                        continue
                    resumen.append([str(etiqueta),
                                    visor._fmt(valor, sf.cell(r, 5).number_format)])
                clase = ("ok" if estado.startswith("CALCULADO")
                         else "bad" if estado.startswith("NO SOPORTADO") else "pd")
                mdl["vacx"] = {"resumen": resumen, "estado": estado, "clase": clase}
        except Exception:  # noqa: BLE001
            pass
    m07 = _buscar_cedula(carpeta_cedulas, "RQ-007_")
    if m07:
        try:
            wv = openpyxl.load_workbook(m07, data_only=True)
            pob, mue = [], []
            if "Población" in wv.sheetnames:
                wp = wv["Población"]
                # Encabezado en la fila 4; datos desde la 5. Col C=cédula, D=nombre,
                # E=D13, F=D14, J=¿Clave?, M=¿Seleccionado?. Paramos al llegar al TOTAL (D sin cédula).
                for r in range(5, wp.max_row + 1):
                    ced = wp.cell(r, 3).value
                    if ced in (None, ""):
                        continue
                    nom = wp.cell(r, 4).value
                    d13 = wp.cell(r, 5).value
                    d14 = wp.cell(r, 6).value
                    try:
                        d13 = round(float(d13), 2)
                    except (TypeError, ValueError):
                        continue  # fila sin importe (p. ej. la fila TOTAL): no es población
                    try:
                        d14 = round(float(d14), 2)
                    except (TypeError, ValueError):
                        d14 = 0.0
                    pob.append([str(ced), str(nom or ""), d13, d14])
                    if str(wp.cell(r, 13).value or "").strip() == "Sí":
                        tipo = ("Clave (mayor D13)"
                                if str(wp.cell(r, 10).value or "").strip() == "Sí"
                                else "Sistemática")
                        mue.append([str(ced), str(nom or ""), d13, d14, tipo])
            par = {}
            if "Ficha" in wv.sheetnames:
                f = wv["Ficha"]
                pct = f.cell(10, 3).value  # C10: tamaño de muestra (fracción, p. ej. 0.10)
                if isinstance(pct, (int, float)):
                    par["pct"] = int(round(pct * 100)) if pct <= 1 else int(round(pct))
                for clave, fila in (("key", 11), ("st", 12)):
                    v = f.cell(fila, 3).value
                    if isinstance(v, (int, float)):
                        par[clave] = int(v)
            tot = {}
            if "Parámetros" in wv.sheetnames:
                q = wv["Parámetros"]
                for clave, fila in (("N", 4), ("d14", 5), ("n", 6), ("itv", 10)):
                    v = q.cell(fila, 3).value  # C4/C5/C6/C10
                    if isinstance(v, (int, float)):
                        tot[clave] = round(float(v), 2) if clave == "itv" else int(v)
            if pob:
                mdl["m07"] = {"pob": pob, "par": par, "tot": tot, "mue": mue}
        except Exception:  # noqa: BLE001
            pass
    k08 = _buscar_cedula(carpeta_cedulas, "RQ-008_")
    if k08:
        try:
            wk = openpyxl.load_workbook(k08, data_only=True)
            # Hoja del kárdex: cuenta de trabajadores (filas con cédula desde la 6).
            ws = next((wk[t] for t in ("Kárdex RQ-008", "Kárdex", "Kardex") if t in wk.sheetnames), None)
            filas = 0
            if ws is not None:
                for r in range(6, ws.max_row + 1):
                    if ws.cell(r, 3).value not in (None, ""):
                        filas += 1
            mdl["k08"] = {"filas": filas}
        except Exception:  # noqa: BLE001
            pass
    return mdl


def derivar_nt(carpeta_cedulas: str | None) -> int | None:
    """Número de «trabajadores activos al corte» tomado del MOTOR, para el valor por defecto
    del cuestionario de control interno DO-1 (su aplicabilidad depende del Nº de trabajadores:
    ítems 33 ≥25, 36/41 ≥50, 44 1–10, 45/48/49 >10, 46/47 ≥10).

    Fuente: la fila «Trabajadores activos al corte (población 100%)» del RESUMEN de la cédula
    VAC (hoja «VAC Calculadora»): etiqueta en la columna A (merged A:D) y valor recalculado en
    la columna E, filas 9..20. Esa celda es ``=COUNTA(B30:B…)`` sobre el 100% de la población
    activa al corte (ver ``nomina/mk_vac.py`` línea 130). Es la fuente más defendible: el mismo
    conteo que el motor usa para valorar vacaciones no gozadas.

    LÍMITE HONESTO: es el conteo de trabajadores ACTIVOS AL CORTE, no el total de personas que
    pasaron por el rol durante el año (ese sería mayor). Para los umbrales IESS/MDT del DO-1 el
    número al corte es el pertinente. El auditor puede sobrescribirlo a mano en el panel.

    Devuelve un entero > 0, o ``None`` si la prueba no está procesada, no hay cédula VAC, o el
    valor aún no está recalculado por LibreOffice (celda sin valor en caché). Con ``None`` el
    panel se comporta como hoy: el auditor digita el número manualmente.
    """
    if not (carpeta_cedulas and os.path.isdir(carpeta_cedulas)):
        return None
    import openpyxl

    vac = _buscar_cedula(carpeta_cedulas, "VAC_")
    if not vac:
        return None
    try:
        wv = openpyxl.load_workbook(vac, data_only=True)
        if "VAC Calculadora" not in wv.sheetnames:
            return None
        ws = wv["VAC Calculadora"]
        for r in range(9, 21):
            etiqueta = str(ws.cell(r, 1).value or "")
            if etiqueta.startswith("Trabajadores activos al corte"):
                valor = ws.cell(r, 5).value
                try:
                    n = int(round(float(valor)))
                except (TypeError, ValueError):
                    return None
                return n if n > 0 else None
    except Exception:  # noqa: BLE001
        return None
    return None


def construir_files(archivos: list | None) -> list:
    """Normaliza los archivos cargados a la prueba al formato que agrupa el panel en sus
    casilleros: ``[{req, comp, name, size, estado, id}]``. El panel (JS) los reparte en
    FILES por requerimiento y, cuando el requerimiento tiene compartimentos (RQ-003 por
    región, RQ-004 pasivos/gastos, RQ-005 por tipo), por el nombre del compartimento.
    Ignora los archivos rechazados (no cubren el requerimiento)."""
    out = []
    for a in archivos or []:
        estado = getattr(a, "estado", None) or (a.get("estado") if isinstance(a, dict) else None)
        get = (lambda k: getattr(a, k, None)) if not isinstance(a, dict) else (lambda k: a.get(k))
        out.append({
            "req": str(get("requerimiento") or ""),
            "comp": str(get("componente") or ""),
            "name": str(get("nombre") or ""),
            "size": int(get("tamano") or 0),
            "estado": str(estado or "recibido"),
            "id": get("id"),
        })
    return out


def render(engagement: dict, prueba_id: int | None = None, base: str = "/aud/ciclo",
           carpeta_cedulas: str | None = None, extras: dict | None = None,
           do1_estado: dict | None = None, archivos: list | None = None,
           embed: bool = False) -> bytes:
    """HTML del panel con el encargo inyectado. ``prueba_id`` enlaza los botones al motor.

    ``carpeta_cedulas``: carpeta con las cédulas YA RECALCULADAS (LibreOffice) que produjo el
    motor para esta prueba. Si viene, el visor del panel muestra cada cédula pestaña por pestaña
    (patrón artefacto, como la planificación) y la ventana de Vacaciones (DO-4V) se alimenta de
    la cédula VAC / kárdex RQ-008.

    ``extras``: ``{'prog': prog.json, 'do12': do12.json}`` que el motor dejó en ``home`` (los
    pasa el endpoint vía ``servicio.correr_nomina(..., con_extras=True)``). Alimentan las
    ventanas Programa (DO-0) y Hallazgos/Ajustes (DO-12).

    El placeholder ``__NOMINA_NT__`` lleva el Nº de trabajadores activos al corte derivado del
    motor (``derivar_nt``): el cuestionario DO-1 lo usa como valor por defecto de ``S.nt`` para
    resolver la aplicabilidad de los ítems por umbral sin que el auditor lo digite (``null`` sin
    procesar; el auditor siempre puede sobrescribirlo).

    ``do1_estado`` es el estado guardado del cuestionario DO-1 dentro de la prueba
    (``servicio.leer_do1``): se inyecta en ``__NOMINA_DO1__`` para que el panel PRECARGUE las
    respuestas del auditor desde la prueba (fuente de verdad) en vez del ``localStorage`` del
    navegador. ``None`` → el panel cae a su borrador local, como antes.

    Sin ``extras`` ni ``carpeta_cedulas`` (prueba no procesada) el panel inyecta estructuras
    VACÍAS y las ventanas muestran «PENDIENTE DE PROCESAR», como el visor.

    ``embed``: True devuelve el panel listo para INCRUSTARSE en el Command Center (en un
    ``<iframe>``), sin su barra superior propia para no duplicar la cabecera (ver ``_EMBED_CSS``);
    False (por defecto) lo deja como HTML autónomo para abrirlo en una pestaña suelta."""
    from backend.app.aud.niif.procesadores.nomina import visor

    enc = construir_encargo(engagement)
    api = {"base": base, "pruebaId": prueba_id}
    with open(_TMPL, encoding="utf-8") as fh:
        tmpl = fh.read()
    datos_visor = None
    if carpeta_cedulas and os.path.isdir(carpeta_cedulas):
        datos_visor = visor.empaquetar(carpeta_cedulas)
    prog = construir_prog(extras)
    mdl = construir_mdl(carpeta_cedulas)
    # La población del muestreo DO-4 V08 sale del motor (MDL.m07.pob, cédula RQ-007).
    # Sin cédula procesada → lista vacía: la ventana muestra «PENDIENTE DE PROCESAR».
    pop07 = (mdl.get("m07") or {}).get("pob", [])
    # Nº de trabajadores activos al corte tomado del motor (cédula VAC). Valor por defecto del
    # cuestionario DO-1 para que la aplicabilidad (autoNA/eff) se resuelva sola; None sin procesar.
    nt = derivar_nt(carpeta_cedulas)
    # Archivos YA cargados a la prueba (requerimiento, componente, nombre, tamaño, estado): el
    # panel los agrupa en sus casilleros (FILES) para que al reabrir/refrescar reflejen la carga
    # real, no una simulación en memoria. ``None`` → lista vacía (nada cargado todavía).
    files_init = construir_files(archivos)
    html = (tmpl
            .replace("__NOMINA_ENC__", json.dumps(enc, ensure_ascii=False))
            .replace("__NOMINA_API__", json.dumps(api, ensure_ascii=False))
            .replace("__NOMINA_MARCA__", json.dumps(marca_panel(engagement)))
            .replace("__NOMINA_PROG__", json.dumps(prog, ensure_ascii=False))
            .replace("__NOMINA_MDL__", json.dumps(mdl, ensure_ascii=False))
            .replace("__NOMINA_POP07__", json.dumps(pop07, ensure_ascii=False))
            .replace("__NOMINA_NT__", json.dumps(nt))
            .replace("__NOMINA_DO1__", json.dumps(do1_estado, ensure_ascii=False))
            .replace("__NOMINA_FILES__", json.dumps(files_init, ensure_ascii=False))
            .replace("__NOMINA_VISOR__", json.dumps(datos_visor)))
    if embed:
        # El panel se incrusta en el Command Center (iframe): oculta su propia barra superior
        # para no duplicar la cabecera del Command Center. Ver ``_EMBED_CSS``.
        html = html.replace("</head>", _EMBED_CSS + "</head>", 1)
    return html.encode("utf-8")
