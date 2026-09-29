"""Revisor genérico por contrato para las herramientas NIIF del catálogo.

No construye la prueba: la **revisa** sobre lo que devolvió su procesador,
emitiendo el mismo veredicto que la consola de planificación (APTO PARA REVISIÓN
DEL SOCIO / OBSERVADO / NO APTO). La aprobación final es humana (compuerta del socio).

Controles genéricos (valen para toda herramienta que cumple el contrato):
- **Recálculo independiente del resultado principal por rubro** (si hay módulo
  ``revision/recalc/<processor>.py``): re-deriva ``auditado = registrado + ajuste``
  desde los datos crudos del ``detalle`` con una segunda implementación. Diverge → NO APTO.
- **Panel ejecutivo resuelto**: ``graficos.panel(...)["faltan"]`` vacío (los mismos
  gráficos y tarjetas del HTML se resuelven). No resuelve → NO APTO.
- **Sin cifras pegadas**: todo problema con importe distinto de cero tiene su
  entrada en ``REF_PROBLEMAS`` (se enlaza a la celda que lo origina). Falta → NO APTO.
- **Resultado principal presente** y **cédulas del papel armadas**: si no, OBSERVADO.

Las **excepciones** de la prueba son los hallazgos de auditoría que la herramienta
detecta (su salida esperada): se resumen para el auditor pero no bajan el veredicto;
lo que se juzga es la **calidad del papel de trabajo**, no los hallazgos en sí.
"""
from __future__ import annotations

import datetime

from backend.app.aud.niif.ciclo.revision.recalc import TOL_RECALCULO, recalculo_de
from backend.app.aud.niif.procesadores import graficos

REVISOR_VERSION = "1.0.0"
ETIQUETA_PENDIENTE = "REVISIÓN PRELIMINAR — PENDIENTE DE APROBACIÓN DEL SOCIO"
TOL_IMPORTE = 0.006


def _num(v):
    if isinstance(v, dict):
        v = v.get("v")
    if isinstance(v, bool) or v in (None, ""):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# --- recálculo independiente del resultado principal (a medida por rubro) ------------------------------------

def _bloque_recalculo(run: dict, processor: str) -> dict | None:
    """Normaliza el recálculo del rubro a la forma de un bloque de la consola.

    ``None`` si el rubro todavía no tiene módulo de recálculo. La forma
    (``total``/``diferencias``/``conforme``/``detalle``) es la misma que usan los
    bloques de la planificación, para que el frontend los pinte igual.
    """
    fn = recalculo_de(processor)
    if fn is None:
        return None
    rec = fn(run) or {}
    comps = rec.get("componentes") or []
    if comps:
        filas = [{"etiqueta": c.get("concepto"), "declarado": c.get("declarado"),
                  "recalculado": c.get("recalculado"), "diff": c.get("diff"), "ok": bool(c.get("ok"))}
                 for c in comps]
    else:
        filas = [{"etiqueta": rec.get("etiqueta") or "Resultado principal", "declarado": rec.get("declarado"),
                  "recalculado": rec.get("recalculado"), "diff": rec.get("diff"), "ok": bool(rec.get("ok"))}]
    difs = sum(0 if f["ok"] else 1 for f in filas)
    return {"etiqueta": rec.get("etiqueta") or "Resultado principal", "total": len(filas),
            "diferencias": difs, "conforme": difs == 0 and bool(rec.get("ok", True)),
            "declarado": rec.get("declarado"), "recalculado": rec.get("recalculado"),
            "diff": rec.get("diff"), "detalle": filas}


# --- panel ejecutivo (los gráficos/tarjetas del HTML resuelven) ----------------------------------------------

def _panel_faltan(mod, run: dict, hojas: list) -> list:
    try:
        return graficos.panel(mod, run, hojas).get("faltan") or []
    except Exception as e:  # noqa: BLE001  (un panel que revienta es, en sí, un hallazgo del papel)
        return [f"panel: {e}"]


# --- sin cifras pegadas: todo problema con importe está enlazado a su celda ----------------------------------

def _problemas_sin_enlazar(mod, run: dict) -> list:
    refp = getattr(mod, "REF_PROBLEMAS", {}) or {}
    sin = []
    for e in run.get("exceptions") or []:
        imp = _num(e.get("amount"))
        if imp is not None and abs(imp) > TOL_IMPORTE and e.get("code") not in refp:
            sin.append(e.get("code"))
    # únicos, en orden de aparición
    vistos, out = set(), []
    for c in sin:
        if c not in vistos:
            vistos.add(c)
            out.append(c)
    return out


# --- resumen de los hallazgos de la prueba (informativo, no baja el veredicto) -------------------------------

def _resumen_problemas(run: dict) -> dict:
    exc = run.get("exceptions") or []
    por_tipo: dict = {}
    importe = 0.0
    for e in exc:
        cod = e.get("code", "?")
        por_tipo[cod] = por_tipo.get(cod, 0) + 1
        importe += abs(_num(e.get("amount")) or 0.0)
    return {"total": len(exc), "por_tipo": por_tipo, "importe_total": round(importe, 2)}


# --- cobertura del papel de trabajo --------------------------------------------------------------------------

def _cobertura(recalc: dict | None, panel_faltan: list, sin_enlazar: list,
               hojas: list, primary_ok: bool) -> dict:
    filas = [
        {"capacidad": "Resultado principal calculado (NIA 500)", "presente": primary_ok},
        {"capacidad": "Cédulas del papel armadas", "presente": bool(hojas)},
        {"capacidad": "Panel ejecutivo resuelto (mismos gráficos del HTML)", "presente": not panel_faltan},
        {"capacidad": "Sin cifras pegadas: problemas enlazados a su celda", "presente": not sin_enlazar},
        {"capacidad": "Recálculo independiente del resultado principal (por rubro)",
         "presente": recalc["conforme"] if recalc else False,
         "no_aplica": recalc is None},
    ]
    contables = [f for f in filas if not f.get("no_aplica")]
    presentes = sum(1 for f in contables if f["presente"])
    total = len(contables)
    ver = "CONFORME" if presentes == total else "CON OBSERVACIONES" if presentes >= total - 1 else "NO CONFORME"
    return {"total": total, "presentes": presentes, "veredicto": ver, "detalle": filas}


# --- puerta de calidad (checklist) ---------------------------------------------------------------------------

def _puerta_calidad(recalc: dict | None, panel_faltan: list, sin_enlazar: list,
                    primary_ok: bool, hojas: list) -> list:
    if recalc is None:
        estado_rec, det_rec = "PENDIENTE", "Este rubro aún no tiene recálculo independiente a medida."
    elif recalc["conforme"]:
        estado_rec, det_rec = "PASA", f"{recalc['total']} cifra(s) coinciden con el recálculo independiente."
    else:
        estado_rec, det_rec = "FALLA", f"{recalc['diferencias']} de {recalc['total']} cifra(s) con diferencia."
    return [
        {"criterio": "Resultado principal calculado (NIA 500)",
         "estado": "PASA" if primary_ok else "REVISAR",
         "detalle": "El resultado principal de la prueba tiene valor." if primary_ok
                    else "El resultado principal quedó sin calcular."},
        {"criterio": "Cédulas del papel armadas",
         "estado": "PASA" if hojas else "FALLA",
         "detalle": f"{len(hojas)} cédula(s) en el papel." if hojas else "El papel no tiene cédulas."},
        {"criterio": "Recálculo independiente del resultado principal", "estado": estado_rec, "detalle": det_rec},
        {"criterio": "Panel ejecutivo resuelto (mismos gráficos del HTML)",
         "estado": "PASA" if not panel_faltan else "FALLA",
         "detalle": "Todas las tarjetas y gráficos del panel resuelven." if not panel_faltan
                    else "No resuelven: " + ", ".join(panel_faltan)},
        {"criterio": "Sin cifras pegadas: problemas enlazados a su celda (decisión del dueño)",
         "estado": "PASA" if not sin_enlazar else "FALLA",
         "detalle": "Todo problema con importe remite a la celda que lo origina." if not sin_enlazar
                    else "Problemas con importe sin enlazar: " + ", ".join(sin_enlazar)},
        {"criterio": "Aprobación del socio antes de publicar",
         "estado": "PENDIENTE", "detalle": "Requiere la validación humana del socio."},
    ]


# --- veredicto ------------------------------------------------------------------------------------------------

def revisar(run: dict, mod, processor: str = "") -> dict:
    """Revisa el resultado de una herramienta del catálogo y emite el veredicto.

    ``run`` es el dict que devuelve ``<procesador>.ejecutar`` (con el ``detalle``
    completo). ``mod`` es el módulo del procesador (para ``hojas``, ``PANEL`` y
    ``REF_PROBLEMAS``); ``processor`` es su id (para el recálculo por rubro).
    """
    detalle = run.get("detalle") or {}
    totals = run.get("totals") or {}
    labels = run.get("labels") or {}
    primary = run.get("primary")
    primary_ok = _num(totals.get(primary)) is not None

    try:
        hojas = mod.hojas(run)
    except Exception:  # noqa: BLE001  (un papel que no arma es, en sí, el hallazgo)
        hojas = []

    recalc = _bloque_recalculo(run, processor)
    panel_faltan = _panel_faltan(mod, run, hojas) if hojas else ["panel: sin cédulas"]
    sin_enlazar = _problemas_sin_enlazar(mod, run)
    problemas = _resumen_problemas(run)
    cobertura = _cobertura(recalc, panel_faltan, sin_enlazar, hojas, primary_ok)
    puerta = _puerta_calidad(recalc, panel_faltan, sin_enlazar, primary_ok, hojas)

    bloqueos, hallazgos = [], []
    if recalc is not None and not recalc["conforme"]:
        bloqueos.append(f"El recálculo independiente del resultado principal difiere en "
                        f"{recalc['diferencias']} de {recalc['total']} cifra(s).")
    if panel_faltan:
        bloqueos.append("El panel ejecutivo no resuelve: " + ", ".join(panel_faltan) + ".")
    if sin_enlazar:
        bloqueos.append(f"{len(sin_enlazar)} problema(s) con importe sin enlazar a su celda "
                        f"(cifra pegada): " + ", ".join(sin_enlazar) + ".")
    if not primary_ok:
        hallazgos.append("El resultado principal de la prueba quedó sin calcular.")
    if not hojas:
        hallazgos.append("El papel de trabajo no tiene cédulas.")
    if recalc is None:
        hallazgos.append("Este rubro aún no tiene recálculo independiente a medida; el veredicto se apoya en los "
                         "controles genéricos del papel.")

    if bloqueos:
        veredicto = "NO APTO"
    elif hallazgos:
        veredicto = "OBSERVADO"
    else:
        veredicto = "APTO PARA REVISIÓN DEL SOCIO"

    return {
        "modo": "generico",
        "veredicto": veredicto,
        "etiqueta": ETIQUETA_PENDIENTE,
        "aprobacion_socio_requerida": True,
        "bloqueos": bloqueos,
        "hallazgos": hallazgos,
        "recalculo": recalc,
        "cobertura": cobertura,
        "problemas": problemas,
        "puerta_calidad": puerta,
        "contexto": {
            "prueba": (mod.definicion().get("name") if hasattr(mod, "definicion") else None),
            "rubro": (mod.definicion().get("area") if hasattr(mod, "definicion") else None),
            "primary": primary,
            "resultado_rotulo": labels.get(primary, primary),
            "resultado_valor": _num(totals.get(primary)),
            "marco": detalle.get("marco") or detalle.get("_marco"),
            "edicion": detalle.get("edicion"),
            "corte": detalle.get("corte"),
        },
        "revisor_version": REVISOR_VERSION,
        "revisado_en": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
