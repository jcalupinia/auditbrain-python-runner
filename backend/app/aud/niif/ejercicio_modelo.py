"""Ejercicio modelo (solo lectura) de una herramienta NIIF del Command Center.

Corre el procesador sobre sus datos de ejemplo (los del módulo ``ejemplos_pi``
para pérdidas incurridas; el ``ESCENARIOS``/``EJEMPLO`` del propio procesador
para las demás) y arma el recorrido completo de la prueba paso por paso, para
mostrarlo en un panel de solo lectura.

No toca la base de datos, no crea ni modifica encargos ni pruebas y no consume
el estado del ciclo: solo calcula en memoria y devuelve el recorrido. Reutiliza
el mismo armado que ``scripts/papeles_muestra.py`` (run + program + engagement)
y ``libro.{ext}`` para las descargas del papel de muestra.
"""
from __future__ import annotations

from backend.app.aud.niif import procesadores
from backend.app.aud.niif.procesadores import libro

FORMATOS_PAPEL = ("xlsx", "docx", "pptx", "html")

# Nota de norma/NIA por paso del recorrido (qué hace el auditor y qué lo sustenta).
PASOS_NORMA = {
    1: ("Datos del encargo", "NIA 300 · Planificación de la auditoría",
        "El auditor fija el encargo: cliente, RUC, ejercicio, corte y marco contable. Todo el recorrido cuelga de estos datos."),
    2: ("Selección de la prueba", "NIA 315 (Revisada) · Identificación de riesgos",
        "Se elige la herramienta del rubro con riesgo de incorrección: aquí, la valoración de la cartera y su deterioro."),
    3: ("Programa de trabajo", "NIA 330 · Respuestas a los riesgos evaluados",
        "Base técnica (norma contable y NIA) y tratamiento tributario del ejercicio; cada procedimiento responde a un riesgo."),
    4: ("Requerimiento de información", "NIA 500 · Evidencia de auditoría",
        "Se pide a la entidad la información que alimenta la prueba, con formatos aceptados y un ejemplo del formato válido."),
    5: ("Documentación recibida", "NIA 230 · Documentación de auditoría",
        "Se cargan y concilian los anexos. En el ejercicio modelo van «cargados» los ejemplos ficticios."),
    6: ("Ejecución", "NIA 520 · Procedimientos analíticos · NIA 540 · Estimaciones",
        "El motor recalcula la estimación, deja las cédulas trazables y lista los problemas encontrados."),
    7: ("Análisis de resultados", "NIA 540 · Evaluación de la estimación",
        "El auditor interpreta el ajuste propuesto, la evaluación individual y el efecto fiscal/diferido."),
    8: ("Revisión y aprobación", "NIA 220 · Control de calidad · NIA 700 · Conclusión",
        "Revisión del papel y conclusión; el ajuste queda documentado y aprobado."),
    9: ("Descarga final", "NIA 230 · Archivo de la auditoría",
        "El papel de trabajo se descarga en Excel (con fórmulas), Word, PowerPoint y HTML autónomo."),
}


def escenario(mod):
    """(datasets, parametros, corte) del ejemplo de la herramienta, o None si no
    tiene ninguno. Pérdidas incurridas usa el ejemplo rico de ``ejemplos_pi``."""
    if getattr(mod, "__name__", "").endswith("perdidas_incurridas_s11"):
        from backend.app.aud.niif import ejemplos_pi
        e = ejemplos_pi.ejercicio_modelo()
        return e["datasets"], e["parametros"], e["corte"]
    esc = getattr(mod, "ESCENARIOS", None)
    if esc:
        _, datasets, param, corte = esc[0]
        return datasets, param, corte
    ej = getattr(mod, "EJEMPLO", None)
    if ej and ej.get("datasets"):
        return ej["datasets"], ej.get("parametros", {}), ej["corte"]
    return None


def _engagement(d, param, corte):
    marco = param.get("_marco") or (d.get("frameworks") or ["NIIF para las PYMES"])[0]
    return {"client": "Cliente de muestra S.A.", "ruc": "1790000000001", "cutoff": corte, "year": corte[:4],
            "framework": marco, "firm": "AuditConsulting Auditores Cía. Ltda.",
            "preparer": "Ejercicio modelo", "reviewer": "Pendiente"}


def _reg(d, mod, datasets, param, corte):
    """El ``reg`` que consumen ``libro.{ext}`` (igual que papeles_muestra.py)."""
    res = mod.ejecutar(datasets, param, corte)
    res["hojas"] = mod.hojas(res)
    reg = {"run": res, "datasets": datasets, "parameters": param,
           "program": [{**x, "reference": x.get("source", "")} for x in d.get("program", [])],
           "sources": [], "engagement": _engagement(d, param, corte)}
    return reg


def disponible(mod) -> bool:
    return escenario(mod) is not None


def recorrido(d, mod) -> dict:
    """Payload del recorrido de 9 pasos con datos de ejemplo (solo lectura)."""
    esc = escenario(mod)
    if esc is None:
        return {"disponible": False}
    datasets, param, corte = esc
    reg = _reg(d, mod, datasets, param, corte)
    run = reg["run"]
    eng = reg["engagement"]

    def paso(n, **extra):
        titulo, norma, explicacion = PASOS_NORMA[n]
        return {"n": n, "titulo": titulo, "norma": norma, "explicacion": explicacion, **extra}

    prim = run.get("primary")
    cedulas = [{"name": h["name"], "label": h.get("label", h["name"]),
                "cols": h.get("cols", []), "rows": h.get("rows", []), "total": h.get("total")}
               for h in run.get("hojas", [])]
    pasos = [
        paso(1, encargo=eng, marco=eng["framework"]),
        paso(2, herramienta={"nombre": d["name"], "rubro": d.get("area", ""), "marcos": d.get("frameworks") or [],
                             "resumen": d.get("summary", "")}),
        paso(3, base_tecnica={"norma": (d.get("source_pymes") or {}).get("document", ""),
                              "nia": d.get("nia", [])},
             tratamiento_tributario=[str(x) for x in d.get("calculo", []) if "LRTI" in str(x) or "fiscal" in str(x).lower()],
             programa=d.get("program", [])),
        paso(4, requerimientos=d.get("requests", [])),
        paso(5, documentacion=[{"dataset": k, "registros": len(v)} for k, v in (reg["datasets"] or {}).items()]),
        paso(6, resultado={"totales": run.get("totals", {}), "etiquetas": run.get("labels", {}), "principal": prim,
                           "principal_valor": run.get("totals", {}).get(prim)},
             problemas=run.get("exceptions", []), cedulas=cedulas),
        paso(7, analisis={"principal": prim, "etiqueta": run.get("labels", {}).get(prim),
                          "valor": run.get("totals", {}).get(prim),
                          "problemas": len(run.get("exceptions", []))}),
        paso(8, conclusion=("Se propone ajustar la estimación según el recálculo del modelo; el papel queda "
                            "documentado y aprobado en el ejercicio modelo (datos ficticios).")),
        paso(9, formatos=list(FORMATOS_PAPEL)),
    ]
    return {"disponible": True, "ficticio": True,
            "herramienta": {"nombre": d["name"], "rubro": d.get("area", ""), "marcos": d.get("frameworks") or [],
                            "resumen": d.get("summary", "")},
            "encargo": eng, "version_motor": run.get("engine", ""), "pasos": pasos}


def libro_modelo(d, mod, ext: str) -> bytes:
    """Papel de muestra en el formato pedido (xlsx/docx/pptx/html), solo lectura."""
    if ext not in FORMATOS_PAPEL:
        raise ValueError("Formato no soportado.")
    esc = escenario(mod)
    if esc is None:
        raise ValueError("La herramienta no tiene ejercicio modelo.")
    datasets, param, corte = esc
    reg = _reg(d, mod, datasets, param, corte)
    return getattr(libro, ext)(d, reg, [], 1, "MUESTRA")


def herramienta(origen: str):
    """(definicion, modulo) a partir del origen ``proc:<id>``/``ficha:...``. Solo
    resuelve procesadores de catálogo; devuelve (None, None) si no aplica."""
    if origen and origen.startswith("proc:"):
        mod = procesadores.PROCESADORES.get(origen[5:])
        if mod is not None and getattr(mod, "RUBRO", None):
            return mod.definicion(), mod
    return None, None
