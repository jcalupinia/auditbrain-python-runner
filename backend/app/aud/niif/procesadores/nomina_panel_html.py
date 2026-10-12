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


def render(engagement: dict, prueba_id: int | None = None, base: str = "/aud/ciclo",
           carpeta_cedulas: str | None = None, extras: dict | None = None) -> bytes:
    """HTML del panel con el encargo inyectado. ``prueba_id`` enlaza los botones al motor.

    ``carpeta_cedulas``: carpeta con las cédulas YA RECALCULADAS (LibreOffice) que produjo el
    motor para esta prueba. Si viene, el visor del panel muestra cada cédula pestaña por pestaña
    (patrón artefacto, como la planificación) y la ventana de Vacaciones (DO-4V) se alimenta de
    la cédula VAC / kárdex RQ-008.

    ``extras``: ``{'prog': prog.json, 'do12': do12.json}`` que el motor dejó en ``home`` (los
    pasa el endpoint vía ``servicio.correr_nomina(..., con_extras=True)``). Alimentan las
    ventanas Programa (DO-0) y Hallazgos/Ajustes (DO-12).

    Sin ``extras`` ni ``carpeta_cedulas`` (prueba no procesada) el panel inyecta estructuras
    VACÍAS y las ventanas muestran «PENDIENTE DE PROCESAR», como el visor."""
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
    html = (tmpl
            .replace("__NOMINA_ENC__", json.dumps(enc, ensure_ascii=False))
            .replace("__NOMINA_API__", json.dumps(api, ensure_ascii=False))
            .replace("__NOMINA_MARCA__", json.dumps(marca_panel(engagement)))
            .replace("__NOMINA_PROG__", json.dumps(prog, ensure_ascii=False))
            .replace("__NOMINA_MDL__", json.dumps(mdl, ensure_ascii=False))
            .replace("__NOMINA_POP07__", json.dumps(pop07, ensure_ascii=False))
            .replace("__NOMINA_VISOR__", json.dumps(datos_visor)))
    return html.encode("utf-8")
