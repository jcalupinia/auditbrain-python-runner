"""Inversiones e instrumentos financieros (activos): clasificación, costo amortizado con
tasa de interés efectiva, valor razonable, intereses y dividendos, deterioro y reclasificación.

Versión simple que cumple la norma:

1. Clasificación esperada de cada instrumento según el marco del encargo:
   - NIIF completas (NIIF 9 4.1.1–4.1.5): deuda con flujos que son solo pagos de principal e
     intereses (SPPI) → costo amortizado si el modelo es mantener para cobrar (4.1.2), VR con
     cambios en ORI si es cobrar y vender (4.1.2A), VR con cambios en resultados en otro caso
     (4.1.4); patrimonio → VR con cambios en resultados, o en ORI por elección irrevocable si no
     se mantiene para negociar (4.1.4, 5.7.5); derivados y fondos → VR con cambios en resultados.
   - NIIF para las PYMES (2015: Secc. 11 y 12; 2025: Secc. 11 partes I y II): deuda básica
     (11.8 b, 11.9) → costo amortizado (11.14 a); acciones con VR medible → VR con cambios en
     resultados, si no → costo menos deterioro (11.14 c); lo demás → VR con cambios en
     resultados (2015: 12.8; 2025: 11.54). Las PYMES NO tienen la categoría VR con cambios en ORI
     ni clasifican por modelo de negocio.
2. Costo amortizado con la tasa de interés efectiva (NIIF 9 5.4.1 y apéndice A; PYMES 11.15–11.20):
   calendario regular de cupones desde la fecha de adquisición; la TIE periódica iguala el costo
   al valor actual de los flujos (TASA/RATE en Excel, bisección en Python); costo amortizado al
   corte = VA de los flujos restantes a la TIE, más el interés efectivo lineal desde el último cupón; interés del
   ejercicio = costo amortizado final − inicial + cupones cobrados.
3. Valor razonable al corte con su nivel de jerarquía (NIIF 13 72–90; PYMES 2025 Secc. 12
   12.22–12.27; PYMES 2015 11.27) y diferencia contra libros (ganancia o pérdida no registrada).
4. Intereses devengados (TIE) y dividendos con derecho establecido (5.7.1A; PYMES 2025 11.14A y 11.55)
   contra lo registrado.
5. Deterioro: NIIF completas, pérdida esperada = exposición × PD × LGD, 12 meses sin aumento
   significativo del riesgo (5.5.5) y vida entera con él (5.5.3); en VR con cambios en ORI la
   corrección va a ORI y no reduce el importe en libros (5.5.2). PYMES: pérdida incurrida solo con
   evidencia objetiva (11.21) = importe en libros − VA de los flujos estimados a la TIE original
   (11.25 a) costo amortizado; 11.25 b) costo menos deterioro), que con flujos recortados en proporción es importe en libros × % no recuperable.
6. Reclasificación: NIIF completas solo por cambio del modelo de negocio (4.4.1) con el
   tratamiento de 5.6.1–5.6.7; la elección de ORI para patrimonio es irrevocable (5.7.5).
7. Conciliación: medición correcta − saldo en libros − ajuste de deterioro = ajuste propuesto.
"""
from __future__ import annotations

import re
from datetime import date

from backend.app.aud.niif.procesadores.base import (  # noqa: F401  (a_num y filas_mapeadas los usa el ciclo)
    FILA0, MARCO_COMPLETAS, MARCO_PYMES, a_fecha, a_num, campo, edicion_pymes, es_pymes, filas_mapeadas, fx,
    hoja, m as fmt_m, n2, norm, problema, r2, ref, req, suma, validar_campos, validar_definicion_generica,
)

VERSION = "inversiones_instrumentos 1.0"
RUBRO = "INVERSIONES"

_INVERSIONES = [
    campo("id", "Instrumento (código)", alias=("instrumento", "codigo", "titulo", "valor", "isin", "numero")),
    campo("emisor", "Emisor", alias=("emisor", "contraparte", "entidad", "institucion")),
    campo("tipo", "Tipo (deuda, patrimonio, fondo, derivado)", alias=("tipo", "tipo de instrumento", "clase", "naturaleza"),
          ejemplo="Bono / Certificado de depósito / Acciones / Fondo / Derivado"),
    campo("fecha_adq", "Fecha de adquisición", "date", False, ("fecha adquisicion", "fecha de compra", "fecha emision", "adquisicion")),
    campo("vence", "Fecha de vencimiento", "date", False, ("vencimiento", "fecha vencimiento", "vence")),
    campo("nominal", "Valor nominal", "number", False, ("nominal", "valor nominal", "valor facial", "principal")),
    campo("costo", "Costo de adquisición (con costos de transacción)", "number", False, ("costo", "valor de compra", "precio de compra", "costo historico")),
    campo("cupon", "Tasa cupón anual %", "number", False, ("tasa cupon", "cupon", "tasa nominal", "tasa de interes", "tasa")),
    campo("frecuencia", "Pagos de cupón por año", "number", False, ("frecuencia", "pagos por ano", "periodicidad")),
    campo("modelo", "Modelo de negocio", "text", False, ("modelo de negocio", "modelo", "intencion", "objetivo"),
          ejemplo="Mantener para cobrar / Cobrar y vender / Negociar"),
    campo("sppi", "¿Flujos solo principal e intereses? (Sí/No) (NIIF completas; en PYMES se evalúan las condiciones de 11.9 a)–d))", "text", False, ("sppi", "solo principal e intereses", "instrumento basico", "basico")),
    campo("clasificacion", "Clasificación del cliente", alias=("clasificacion", "categoria", "clasificacion cliente", "medicion"),
          ejemplo="Costo amortizado / VR con cambios en ORI / VR con cambios en resultados / Costo"),
    campo("valor_razonable", "Valor razonable al corte", "number", False, ("valor razonable", "valor de mercado", "precio de mercado", "vr")),
    campo("nivel", "Nivel de jerarquía (1, 2 o 3)", "number", False, ("nivel", "jerarquia", "nivel de jerarquia")),
    campo("saldo_libros", "Saldo en libros (bruto)", "number", True, ("saldo", "saldo en libros", "saldo contable", "valor en libros")),
    campo("ingreso_registrado", "Intereses o dividendos registrados en el ejercicio", "number", False,
          ("intereses registrados", "ingreso registrado", "rendimiento registrado", "dividendos registrados")),
    campo("dividendos", "Dividendos decretados en el ejercicio", "number", False, ("dividendos decretados", "dividendos")),
    campo("deterioro_registrado", "Deterioro / corrección de valor registrada", "number", False, ("deterioro registrado", "provision", "correccion de valor")),
    campo("calificacion", "Calificación de riesgo", "text", False, ("calificacion", "rating", "calificacion de riesgo")),
    campo("indicio", "¿Indicio de deterioro o aumento significativo del riesgo? (Sí/No)", "text", False, ("indicio", "indicio de deterioro", "deteriorado")),
    campo("pd", "Probabilidad de incumplimiento % (PD)", "number", False, ("pd", "probabilidad de incumplimiento")),
    campo("lgd", "Pérdida dado el incumplimiento % (LGD) / % no recuperable", "number", False, ("lgd", "severidad", "perdida dado el incumplimiento", "no recuperable")),
    campo("clasificacion_anterior", "Clasificación al cierre anterior", "text", False, ("clasificacion anterior", "categoria anterior")),
    campo("cambio_modelo", "¿Cambio documentado del modelo de negocio? (Sí/No)", "text", False, ("cambio de modelo", "cambio modelo")),
]
CAMPOS = {"inversiones": _INVERSIONES}
TIPOS = {"inversiones": "inversiones"}
DATASETS = tuple(TIPOS)
PRINCIPAL = "inversiones"
CONTROL = "saldo_libros"

PARAMETROS = {"frecuenciaDefecto": 1}
PARAM_NEGATIVOS = ()
ETIQUETAS_PARAM = {"frecuenciaDefecto": "Pagos de cupón por año cuando el anexo no lo indica"}
TOTAL_EJEMPLO = "ajuste"

CLASES = {"CA": "Costo amortizado", "VRORI": "VR con cambios en ORI", "VRR": "VR con cambios en resultados", "COSTO": "Costo menos deterioro"}
FRECUENCIAS = (1, 2, 3, 4, 6, 12)


def kind(dataset: str) -> str:
    return TIPOS[dataset]


def validar_filas(tipo: str, filas: list) -> dict:
    r = validar_campos(CAMPOS[tipo], filas)
    for f in filas:
        fila = f.get("_row")
        for k, lo, hi in (("pd", 0, 100), ("lgd", 0, 100), ("cupon", 0, 100)):
            v = a_num(f.get(k)) if str(f.get(k, "") or "").strip() else None
            if v is not None and not lo <= v <= hi:
                r["errors"].append({"row": fila, "field": k, "message": f"{k.upper()}: use un porcentaje entre 0 y 100."})
        nv = a_num(f.get("nivel")) if str(f.get("nivel", "") or "").strip() else None
        if nv is not None and nv not in (1, 2, 3):
            r["errors"].append({"row": fila, "field": "nivel", "message": "Nivel de jerarquía: 1, 2 o 3."})
        fr = a_num(f.get("frecuencia")) if str(f.get("frecuencia", "") or "").strip() else None
        if fr is not None and fr not in FRECUENCIAS:
            r["errors"].append({"row": fila, "field": "frecuencia", "message": "Pagos por año: 1, 2, 3, 4, 6 o 12."})
    r["ok"] = not r["errors"]
    return r


# --- normalización (el Excel compara estos textos) -----------------------------------

def _tipo(v) -> str:
    n = norm(v)
    if not n:
        return ""
    if any(x in n for x in ("deriv", "forward", "swap", "opcion", "futuro")):
        return "Derivado"
    if "fondo" in n:
        return "Fondo"
    if any(x in n for x in ("accion", "patrimon", "particip", "capital")):
        return "Patrimonio"
    return "Deuda"


def _modelo(v) -> str:
    n = norm(v)
    if "vender" in n or "venta" in n or "ambos" in n:
        return "Cobrar y vender"
    if "negoci" in n or "trading" in n:
        return "Negociar"
    if "mantener" in n or "cobrar" in n or "vencimiento" in n:
        return "Mantener para cobrar"
    return ""


def _sino(v) -> str:
    n = norm(v)
    if n in ("si", "s", "yes", "y", "x", "true", "1", "cumple"):
        return "Sí"
    if n in ("no", "n", "false", "0", "nocumple"):
        return "No"
    return ""


def _clase(v) -> str:
    t = str(v if v is not None else "").lower()
    n = norm(v)
    if "amortiz" in n or n == "ca":
        return "CA"
    if re.search(r"\bori\b", t) or "otroresultado" in n or n == "vrori":
        return "VRORI"
    if "resultado" in n or n in ("vrr", "vr", "fvtpl") or "negoci" in n or "razonable" in n:
        return "VRR"
    if "costo" in n or "coste" in n:
        return "COSTO"
    return ""


def _opt(f, k):
    s = str(f.get(k, "") or "").strip()
    return a_num(s) if s else None


# --- aritmética igual a Excel ---------------------------------------------------------

def _edate(d: date, meses: int) -> date:
    import calendar
    y, mth = divmod(d.month - 1 + meses, 12)
    y += d.year
    mth += 1
    return date(y, mth, min(d.day, calendar.monthrange(y, mth)[1]))


def _datedif_m(a: date, b: date) -> int:
    """DATEDIF(a;b;"m"): meses completos."""
    return (b.year - a.year) * 12 + b.month - a.month - (1 if b.day < a.day else 0)


def _pv(r: float, n: float, c: float, nom: float) -> float:
    """PV(r;n;-c;-nom) de Excel (positivo)."""
    if r == 0:
        return c * n + nom
    return c * (1 - (1 + r) ** -n) / r + nom * (1 + r) ** -n


def _tie(n: int, c: float, costo: float, nom: float):
    """TASA(n;c;-costo;nom) por bisección: VA de los flujos a la tasa = costo."""
    lo, hi = -0.99, 10.0
    if not (_pv(lo, n, c, nom) >= costo >= _pv(hi, n, c, nom)):
        return None
    for _ in range(300):
        mid = (lo + hi) / 2
        if _pv(mid, n, c, nom) > costo:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _ca_en(x: dict, d: date) -> dict:
    """Costo amortizado (con cupón corrido) a la fecha d; k = cupones ya cobrados."""
    h, r = x["h"], x["r"]
    k = _datedif_m(x["adq"], d) // h
    a, b = _edate(x["adq"], k * h), _edate(x["adq"], (k + 1) * h)
    frac = (d - a).days / (b - a).days
    base = _pv(r, x["n"] - k, x["c"], x["nominal"])
    return {"k": k, "frac": frac, "base": base, "sucio": base * (1 + r * frac)}   # interés efectivo lineal dentro del período


def _esperada(marco_pymes: bool, tipo: str, modelo: str, sppi: str, cli: str, vr) -> str:
    if marco_pymes:
        if tipo == "Deuda":
            return "" if sppi == "" else ("VRR" if sppi == "No" else "CA")
        if tipo == "Patrimonio":
            return "VRR" if vr is not None else "COSTO"
        return "VRR"
    if tipo == "Deuda":
        if sppi == "":
            return ""
        if sppi == "No":
            return "VRR"
        return {"Mantener para cobrar": "CA", "Cobrar y vender": "VRORI", "Negociar": "VRR"}.get(modelo, "")
    if tipo == "Patrimonio":
        return "VRORI" if cli == "VRORI" and modelo != "Negociar" else "VRR"
    return "VRR"


def _fundamento(pymes: bool, ed: str, x: dict) -> str:
    t, e = x["tipo"], x["esperada"]
    if pymes:
        sec = "Secc. 11 parte I" if ed == "2025" else "Secc. 11"
        otros = "11.54 (parte II)" if ed == "2025" else "Secc. 12, 12.8"
        if t == "Deuda":
            return {"CA": f"Deuda básica (11.8 b, 11.9): costo amortizado con TIE, 11.14 a ({sec}).",
                    "VRR": f"Deuda que no cumple 11.9: VR con cambios en resultados ({otros})."}.get(e, "Indique si los flujos cumplen 11.9 (solo principal e intereses).")
        if t == "Patrimonio":
            return ("Acciones con VR medible con fiabilidad: VR con cambios en resultados, 11.14 c i." if e == "VRR"
                    else "Acciones sin VR fiable: costo menos deterioro, 11.14 c ii.")
        return f"Instrumento no básico: VR con cambios en resultados ({otros})."
    if t == "Deuda":
        if e == "":
            return "Falta evaluar SPPI (4.1.2 b) o el modelo de negocio (4.1.1 a, B4.1.1)."
        return {"CA": "SPPI y mantener para cobrar: costo amortizado (4.1.2).",
                "VRORI": "SPPI y cobrar y vender: VR con cambios en ORI (4.1.2A).",
                "VRR": "No SPPI o modelo de negociación: VR con cambios en resultados (4.1.4); designación 4.1.5 solo si elimina una asimetría."}[e]
    if t == "Patrimonio":
        return ("Elección irrevocable de ORI para patrimonio no mantenido para negociar (4.1.4, 5.7.5, B5.7.1); dividendos a resultados (5.7.6)."
                if e == "VRORI" else "Patrimonio: VR con cambios en resultados (4.1.4).")
    return "Derivado o participación en fondo: VR con cambios en resultados (4.1.4; fondos: flujos no SPPI, VERIFICAR B4.1.7–B4.1.26)."


_TRAT = {
    ("CA", "VRR"): "VR a la fecha de reclasificación; diferencia con el costo amortizado a resultados (5.6.2).",
    ("VRR", "CA"): "El VR a la fecha de reclasificación pasa a ser el importe en libros bruto (5.6.3, B5.6.2).",
    ("CA", "VRORI"): "VR a la fecha de reclasificación; diferencia a ORI; TIE y pérdida esperada no cambian (5.6.4).",
    ("VRORI", "CA"): "Se reclasifica al VR y se elimina lo acumulado en ORI contra el importe en libros (5.6.5).",
    ("VRR", "VRORI"): "Se sigue midiendo a VR (5.6.6, B5.6.2).",
    ("VRORI", "VRR"): "Se sigue midiendo a VR; lo acumulado en ORI pasa a resultados (5.6.7).",
}


# --- cálculo --------------------------------------------------------------------------

def ejecutar(datasets: dict, parametros: dict, corte: str) -> dict:
    p = {**PARAMETROS, **{k: v for k, v in (parametros or {}).items() if v is not None and v != ""}}
    corte_a = a_fecha(corte)
    if corte_a is None:
        raise ValueError("Indique la fecha de corte del encargo.")
    frec_def = a_num(p.get("frecuenciaDefecto"))
    if frec_def not in FRECUENCIAS:
        raise ValueError("Pagos de cupón por año: use 1, 2, 3, 4, 6 o 12.")
    pymes, ed = es_pymes(p), edicion_pymes(p)
    inicio = _edate(corte_a, -12)
    filas = [f for f in datasets.get("inversiones") or [] if str(f.get("id", "") or "").strip()]
    if not filas:
        raise ValueError("Cargue el anexo de inversiones al corte (una fila por instrumento).")

    inst = []
    for f in filas:
        libros = a_num(f.get("saldo_libros"))
        if libros is None:
            raise ValueError(f"Instrumento {f.get('id')}: falta el saldo en libros.")
        x = {"id": str(f.get("id")).strip(), "emisor": str(f.get("emisor", "") or "").strip(), "_row": f.get("_row"),
             "tipo": _tipo(f.get("tipo")), "modelo": _modelo(f.get("modelo")), "sppi": _sino(f.get("sppi")),
             "clienteTxt": str(f.get("clasificacion", "") or "").strip(), "cliente": _clase(f.get("clasificacion")),
             "adq": a_fecha(f.get("fecha_adq")), "vence": a_fecha(f.get("vence")), "nominal": _opt(f, "nominal"),
             "costo": _opt(f, "costo"), "cupon": _opt(f, "cupon"), "frec": int(_opt(f, "frecuencia") or frec_def),
             "libros": libros, "vr": _opt(f, "valor_razonable"),
             "nivel": int(_opt(f, "nivel")) if _opt(f, "nivel") is not None else None,
             "detReg": _opt(f, "deterioro_registrado"), "ingReg": _opt(f, "ingreso_registrado"),
             "divid": _opt(f, "dividendos"), "calif": str(f.get("calificacion", "") or "").strip(),
             "indicio": _sino(f.get("indicio")), "pd": _opt(f, "pd"), "lgd": _opt(f, "lgd"),
             "anterior": _clase(f.get("clasificacion_anterior")), "anteriorTxt": str(f.get("clasificacion_anterior", "") or "").strip(),
             "cambio": _sino(f.get("cambio_modelo"))}
        if x["frec"] not in FRECUENCIAS:
            raise ValueError(f"Instrumento {x['id']}: pagos por año 1, 2, 3, 4, 6 o 12.")
        x["esperada"] = _esperada(pymes, x["tipo"], x["modelo"], x["sppi"], x["cliente"], x["vr"])
        x["consistente"] = "" if x["esperada"] == "" else ("Sí" if x["esperada"] == x["cliente"] else "No")
        x["fundamento"] = _fundamento(pymes, ed, x)
        x["vencido"] = x["vence"] is not None and x["vence"] <= corte_a
        inst.append(x)

    # 2 · costo amortizado con TIE (deuda con datos completos, vigente y adquirida hasta el corte).
    for x in inst:
        x["ca"] = None
        ok = (x["tipo"] == "Deuda" and x["adq"] and x["vence"] and x["nominal"] and x["costo"] and x["cupon"] is not None
              and x["adq"] <= corte_a < x["vence"])
        if not ok:
            continue
        h = 12 // x["frec"]
        n = int(_datedif_m(x["adq"], x["vence"]) / h + 0.5)   # ROUND de Excel
        # ponytail: calendario regular desde la adquisición; cupones irregulares o compra entre cupones → tabla de flujos propia.
        if n < 1:
            continue
        c = x["nominal"] * x["cupon"] / 100 / x["frec"]
        r = _tie(n, c, x["costo"], x["nominal"])
        if r is None:
            continue
        x.update(h=h, n=n, c=c, r=r)
        fin = _ca_en(x, corte_a)
        if x["adq"] > inicio:
            ki, ini = 0, x["costo"]
        else:
            ci = _ca_en(x, inicio)
            ki, ini = ci["k"], ci["sucio"]
        x["ca"] = {"h": h, "n": n, "c": c, "r": r, "anual": (1 + r) ** x["frec"] - 1, "control": _pv(r, n, c, x["nominal"]) - x["costo"],
                   "k": fin["k"], "frac": fin["frac"], "base": fin["base"], "sucio": fin["sucio"], "corrido": c * fin["frac"],
                   "limpio": fin["sucio"] - c * fin["frac"], "ki": ki, "ini": ini, "cupones": c * (fin["k"] - ki),
                   "interes": fin["sucio"] - ini + c * (fin["k"] - ki)}

    # 3–7 · valor razonable, ingresos, deterioro, medición y ajuste.
    for x in inst:
        e, ca = x["esperada"], x["ca"]
        x["difVR"] = (x["vr"] - x["libros"]) if e in ("VRR", "VRORI") and x["vr"] is not None else None
        if x["tipo"] == "Deuda":
            x["ingEsp"] = ca["interes"] if ca and e in ("CA", "VRORI") else None
        elif x["tipo"] == "Patrimonio":
            x["ingEsp"] = x["divid"]
        else:
            x["ingEsp"] = None
        x["ingDif"] = None if x["ingEsp"] is None else x["ingEsp"] - (x["ingReg"] or 0)
        if pymes:
            aplica = e in ("CA", "COSTO")
            x["base"] = (ca["sucio"] if ca else None) if e == "CA" else (x["costo"] if e == "COSTO" else None)
            if not aplica:
                x["detCalc"] = None
            elif x["indicio"] != "Sí":
                x["detCalc"] = 0.0
            else:
                x["detCalc"] = None if x["base"] is None or x["lgd"] is None else x["base"] * x["lgd"] / 100
            x["enfoque"] = ("No aplica" if not aplica else
                            ("Pérdida incurrida (11.21, 11.25)" if x["indicio"] == "Sí" else "Sin evidencia objetiva: sin pérdida (11.21)"))
        else:
            aplica = e == "CA" or (e == "VRORI" and x["tipo"] == "Deuda")   # 5.5.1: el patrimonio no se deteriora
            x["base"] = ca["sucio"] if ca and aplica else None
            x["detCalc"] = (None if not aplica or x["base"] is None or x["pd"] is None or x["lgd"] is None
                            else x["base"] * x["pd"] / 100 * x["lgd"] / 100)
            x["enfoque"] = "No aplica" if not aplica else ("Vida entera (5.5.3)" if x["indicio"] == "Sí" else "12 meses (5.5.5)")
        x["detDif"] = None if x["detCalc"] is None else x["detCalc"] - (x["detReg"] or 0)
        x["medicion"] = ((ca["limpio"] if ca else None) if e == "CA" else x["vr"] if e in ("VRR", "VRORI")
                         else x["costo"] if e == "COSTO" else None)
        x["difMed"] = None if x["medicion"] is None else x["medicion"] - x["libros"]
        x["ajDet"] = (None if x["detCalc"] is None else x["detCalc"] - (x["detReg"] or 0)) if e in ("CA", "COSTO") else 0.0
        x["ajuste"] = None if x["difMed"] is None or x["ajDet"] is None else x["difMed"] - x["ajDet"]
        # reclasificación
        x["permitido"] = ""
        if x["anterior"]:
            if x["anterior"] == x["cliente"]:
                x["permitido"] = "Sin cambio"
            elif pymes:
                x["permitido"] = ("Sí: el instrumento cambió de condiciones (VERIFICAR soporte)" if x["cliente"] == e
                                  else "No: la clasificación no corresponde a las condiciones del instrumento")
            elif x["tipo"] == "Patrimonio" and x["anterior"] == "VRORI":
                x["permitido"] = "No: elección irrevocable (5.7.5)"
            elif x["tipo"] == "Deuda" and x["cambio"] == "Sí":
                x["permitido"] = "Sí: cambio de modelo de negocio (4.4.1)"
            else:
                x["permitido"] = "No: sin cambio de modelo de negocio (4.4.1)"
            x["tratamiento"] = ("PYMES: sin reclasificación por modelo de negocio; la medición sigue las condiciones del instrumento (11.14)."
                                if pymes else _TRAT.get((x["anterior"], x["cliente"]), "Sin tratamiento de reclasificación aplicable."))

    # problemas
    probs = []
    for x in inst:
        i = x["id"]
        if x["vencido"]:
            probs.append(problema("INSTRUMENTO_VENCIDO", f"{i}: venció el {x['vence'].isoformat()} y sigue en libros; confirme cobro o baja (NIIF 9 3.2.3 / PYMES 11.33).", x["libros"]))
        if x["cliente"] == "":
            probs.append(problema("CLASIFICACION_ILEGIBLE", f"{i}: la clasificación del cliente «{x['clienteTxt']}» no se reconoce.", x["libros"]))
        if x["esperada"] == "":
            probs.append(problema("CLASIFICACION_NO_DETERMINABLE", f"{i}: {x['fundamento']}", x["libros"]))
        elif x["consistente"] == "No":
            extra = " Las PYMES no tienen la categoría VR con cambios en ORI." if pymes and x["cliente"] == "VRORI" else ""
            probs.append(problema("CLASIFICACION_INCONSISTENTE", f"{i}: el cliente lo clasifica como {CLASES.get(x['cliente'], x['clienteTxt'] or '—')} "
                                  f"y según el modelo de negocio/marco corresponde {CLASES[x['esperada']]}. {x['fundamento']}{extra}", x["libros"]))
        if x["esperada"] == "CA" and not x["vencido"] and x["ca"] is None:
            probs.append(problema("CA_SIN_DATOS", f"{i}: faltan fechas, nominal, costo o cupón para medir el costo amortizado con TIE.", x["libros"]))
        if x["esperada"] == "CA" and x["difMed"] is not None and abs(x["difMed"]) > 0.005:
            probs.append(problema("DIFERENCIA_COSTO_AMORTIZADO", f"{i}: costo amortizado recalculado {fmt_m(x['medicion'])} vs libros {fmt_m(x['libros'])}.", x["difMed"]))
        if x["esperada"] in ("VRR", "VRORI"):
            if x["vr"] is None:
                probs.append(problema("VR_FALTANTE", f"{i}: se mide a valor razonable y no se informó el valor razonable al corte.", x["libros"]))
            elif x["nivel"] is None:
                probs.append(problema("VR_SIN_NIVEL", f"{i}: valor razonable sin nivel de jerarquía (NIIF 13 72–90; PYMES 2025 12.22).", x["vr"]))
            elif x["nivel"] == 3:
                probs.append(problema("VR_NIVEL_3", f"{i}: valor razonable de nivel 3; evalúe supuestos no observables y la conciliación de nivel 3 (NIIF 13 86, 93 e; NIA 540).", x["vr"]))
            if x["difVR"] is not None and abs(x["difVR"]) > 0.005:
                destino = "resultados" if x["esperada"] == "VRR" else "ORI"
                probs.append(problema("DIFERENCIA_VR", f"{i}: valor razonable {fmt_m(x['vr'])} vs libros {fmt_m(x['libros'])}; ganancia/pérdida no registrada en {destino}.", x["difVR"]))
        if x["ingDif"] is not None and abs(x["ingDif"]) > 0.005:
            que = "Intereses devengados (TIE)" if x["tipo"] == "Deuda" else "Dividendos decretados"
            code = ("INTERES_NO_REGISTRADO" if x["tipo"] == "Deuda" else "DIVIDENDO_NO_REGISTRADO") if x["ingDif"] > 0 else "INGRESO_EN_EXCESO"
            probs.append(problema(code, f"{i}: {que} {fmt_m(x['ingEsp'])} vs registrado {fmt_m(x['ingReg'] or 0)}.", x["ingDif"]))
        if x["indicio"] == "Sí":
            probs.append(problema("INDICIO_DETERIORO", f"{i}: indicio de deterioro / aumento significativo del riesgo ({x['calif'] or 'sin calificación'}); enfoque: {x['enfoque']}.", x["detCalc"] or 0))
        elif re.match(r"^(BB|B|C|D)", x["calif"].upper()) and not x["calif"].upper().startswith("BBB") and x["enfoque"] != "No aplica":
            probs.append(problema("CALIFICACION_BAJA_SIN_INDICIO", f"{i}: calificación {x['calif']} (bajo grado de inversión) sin indicio marcado; evalúe aumento significativo del riesgo (5.5.9–5.5.11) o evidencia objetiva (11.22).", x["libros"]))
        if x["enfoque"] != "No aplica" and x["detCalc"] is None and not x["vencido"]:
            probs.append(problema("DETERIORO_SIN_DATOS", f"{i}: faltan {'PD y LGD' if not pymes else '% no recuperable'} o el costo amortizado para medir el deterioro.", x["libros"]))
        if x["detDif"] is not None and abs(x["detDif"]) > 0.005:
            nota = " (en VR con cambios en ORI la corrección va a ORI, 5.5.2)" if x["esperada"] == "VRORI" else ""
            probs.append(problema("DIFERENCIA_DETERIORO", f"{i}: deterioro recalculado {fmt_m(x['detCalc'])} vs registrado {fmt_m(x['detReg'] or 0)}{nota}.", x["detDif"]))
        if x["permitido"].startswith("No"):
            probs.append(problema("RECLASIFICACION_NO_PERMITIDA", f"{i}: pasó de {CLASES.get(x['anterior'])} a {CLASES.get(x['cliente'], '—')}. {x['permitido']}.", x["libros"]))
    sin_med = [x["id"] for x in inst if x["ajuste"] is None]
    if sin_med:
        probs.append(problema("SIN_MEDICION", "Sin medición completa (no suman al ajuste): " + ", ".join(sin_med) + ".", 0))
    tot = lambda k: sum(x[k] for x in inst if x[k] is not None)
    ajuste = tot("ajuste")
    if abs(ajuste) > 0.005:
        probs.append(problema("AJUSTE", f"Ajuste propuesto al importe en libros neto de las inversiones: {fmt_m(ajuste)}.", ajuste))

    rows = [{"id": x["id"], "emisor": x["emisor"], "tipo": x["tipo"], "clasificacion": x["cliente"], "esperada": x["esperada"],
             "saldo_libros": r2(x["libros"]), "medicion": "" if x["medicion"] is None else r2(x["medicion"]),
             "ajuste": "" if x["ajuste"] is None else r2(x["ajuste"]), "_row": x["_row"]} for x in inst]
    totales = {"saldoLibros": r2(tot("libros")), "medicion": r2(tot("medicion")), "difMedicion": r2(tot("difMed")),
               "deterioroCalc": r2(tot("detCalc")), "deterioroReg": r2(sum(x["detReg"] or 0 for x in inst)),
               "ingresoDif": r2(tot("ingDif")), "difVR": r2(tot("difVR")), "ajuste": r2(ajuste)}
    etiquetas = {"saldoLibros": "Saldo en libros (bruto)", "medicion": "Medición según la norma", "difMedicion": "Diferencia de medición",
                 "deterioroCalc": "Deterioro recalculado", "deterioroReg": "Deterioro registrado",
                 "ingresoDif": "Intereses/dividendos no registrados", "difVR": "Diferencia de valor razonable",
                 "ajuste": "Ajuste propuesto (importe neto)"}
    ser = lambda x: {k: (v.isoformat() if isinstance(v, date) else v) for k, v in x.items()}
    detalle = {"corte": corte_a.isoformat(), "inicio": inicio.isoformat(), "pymes": pymes, "edicion": ed,
               "instrumentos": [ser(x) for x in inst], "parametros": p}
    return {"engine": VERSION, "rows": rows, "totals": totales, "labels": etiquetas, "primary": "ajuste",
            "exceptions": probs, "schedule": [], "detalle": detalle}


# --- cédulas con fórmulas -------------------------------------------------------------

CEDULAS = [
    ("01_Resumen", "Resumen"), ("02_Parametros", "Parámetros"), ("03_Inventario", "Inventario de inversiones"),
    ("04_Clasificacion", "Clasificación"), ("05_Costo_amortizado", "Costo amortizado y TIE"),
    ("06_Valor_razonable", "Valor razonable y jerarquía"), ("07_Intereses_dividendos", "Intereses y dividendos"),
    ("08_Deterioro", "Deterioro"), ("09_Reclasificacion", "Reclasificación"), ("10_Conciliacion", "Conciliación y ajuste"),
    ("11_Problemas", "Problemas encontrados"),
]
P, INV, CLA, CAM, VRZ, ING, DET, REC, CON = (ref(n) for n, _ in CEDULAS[1:10])
CORTE, INICIO = f"{P}$B${FILA0}", f"{P}$B${FILA0 + 1}"


def _v(x):
    return "" if x is None else x


def hojas(res: dict) -> list[dict]:
    d = res["detalle"]
    pymes, ed = d["pymes"], d["edicion"]
    xs = d["instrumentos"]
    nx = len(xs)
    fila = {x["id"]: FILA0 + i for i, x in enumerate(xs)}          # misma fila en 03, 04, 07, 08 y 10
    marco = f"{MARCO_PYMES} {ed}" if pymes else MARCO_COMPLETAS

    parametros = [
        ["Fecha de corte", d["corte"], "Ficha del encargo"],
        ["Inicio del ejercicio (un año antes del corte)", d["inicio"], "Base del interés del ejercicio"],
        ["Marco contable", marco, "Enruta clasificación y deterioro"],
        ["Pagos de cupón por año (por defecto)", float(d["parametros"]["frecuenciaDefecto"]), "Solo si el anexo no lo indica"],
        ["CA", CLASES["CA"], "NIIF 9 4.1.2 · PYMES 11.14 a"],
        ["VRORI", CLASES["VRORI"], "NIIF 9 4.1.2A y 5.7.5 · no existe en PYMES"],
        ["VRR", CLASES["VRR"], "NIIF 9 4.1.4 · PYMES 2015 12.8 / 2025 11.54 y 11.14 c i"],
        ["COSTO", CLASES["COSTO"], "Solo PYMES 11.14 c ii"],
    ]

    inventario = [[x["id"], x["emisor"], x["tipo"], x["modelo"], x["sppi"], x["clienteTxt"], x["cliente"], x["adq"], x["vence"],
                   x["nominal"], x["costo"], x["cupon"], float(x["frec"]), x["libros"], x["vr"], x["nivel"], x["detReg"], x["ingReg"],
                   x["divid"], x["indicio"], x["calif"], x["pd"], x["lgd"], x["anterior"], x["cambio"]] for x in xs]

    clasif = []
    for x in xs:
        r = fila[x["id"]]
        if pymes:
            f_esp = f'IF(B{r}="Deuda",IF(D{r}="","",IF(D{r}="No","VRR","CA")),IF(B{r}="Patrimonio",IF(F{r}="Sí","VRR","COSTO"),"VRR"))'
        else:
            f_esp = (f'IF(B{r}="Deuda",IF(D{r}="","",IF(D{r}="No","VRR",IF(C{r}="Mantener para cobrar","CA",IF(C{r}="Cobrar y vender","VRORI",'
                     f'IF(C{r}="Negociar","VRR",""))))),IF(B{r}="Patrimonio",IF(AND(E{r}="VRORI",C{r}<>"Negociar"),"VRORI","VRR"),"VRR"))')
        clasif.append([x["id"], fx(f'{INV}C{r}&""', x["tipo"]), fx(f'{INV}D{r}&""', x["modelo"]), fx(f'{INV}E{r}&""', x["sppi"]),
                       fx(f'{INV}G{r}&""', x["cliente"]), fx(f'IF({INV}O{r}<>"","Sí","No")', "Sí" if x["vr"] is not None else "No"),
                       fx(f_esp, x["esperada"]), fx(f'IF(G{r}="","",IF(G{r}=E{r},"Sí","No"))', x["consistente"]), x["fundamento"]])

    # 05 · costo amortizado
    cam, fila_ca = [], {}
    for x in xs:
        c = x["ca"]
        if not c:
            continue
        r = FILA0 + len(cam)
        fila_ca[x["id"]] = r
        ri = fila[x["id"]]
        frac_i = f"({INICIO}-EDATE(B{r},T{r}*H{r}))/(EDATE(B{r},(T{r}+1)*H{r})-EDATE(B{r},T{r}*H{r}))"
        cam.append([x["id"], x["adq"], x["vence"], fx(f"{INV}J{ri}", x["nominal"]), fx(f"{INV}K{ri}", x["costo"]),
                    fx(f"{INV}L{ri}", x["cupon"]), fx(f"{INV}M{ri}", float(x["frec"])), fx(f"12/G{r}", float(c["h"])),
                    fx(f'ROUND(DATEDIF(B{r},C{r},"m")/H{r},0)', c["n"]), fx(f"D{r}*F{r}/100/G{r}", c["c"]),
                    fx(f"RATE(I{r},J{r},-E{r},D{r})", c["r"]), fx(f"(1+K{r})^G{r}-1", c["anual"]),
                    fx(f"PV(K{r},I{r},-J{r},-D{r})-E{r}", c["control"]),
                    fx(f'INT(DATEDIF(B{r},{CORTE},"m")/H{r})', c["k"]),
                    fx(f"({CORTE}-EDATE(B{r},N{r}*H{r}))/(EDATE(B{r},(N{r}+1)*H{r})-EDATE(B{r},N{r}*H{r}))", c["frac"]),
                    fx(f"PV(K{r},I{r}-N{r},-J{r},-D{r})", c["base"]), fx(f"P{r}*(1+K{r}*O{r})", c["sucio"]),
                    fx(f"J{r}*O{r}", c["corrido"]), fx(f"Q{r}-R{r}", c["limpio"]),
                    fx(f'IF(B{r}>{INICIO},0,INT(DATEDIF(B{r},{INICIO},"m")/H{r}))', c["ki"]),
                    fx(f"IF(B{r}>{INICIO},E{r},PV(K{r},I{r}-T{r},-J{r},-D{r})*(1+K{r}*{frac_i}))", c["ini"]),
                    fx(f"J{r}*(N{r}-T{r})", c["cupones"]), fx(f"Q{r}-U{r}+V{r}", c["interes"])])
    fin_ca = FILA0 + len(cam) - 1

    # 06 · valor razonable
    vrz, fila_vr = [], {}
    for x in xs:
        if x["esperada"] not in ("VRR", "VRORI") and x["vr"] is None:
            continue
        r = FILA0 + len(vrz)
        fila_vr[x["id"]] = r
        ri = fila[x["id"]]
        dest_ori = "ORI sin reciclaje (5.7.5, B5.7.1)" if x["tipo"] == "Patrimonio" else "ORI; intereses y deterioro a resultados (4.1.2A, 5.7.10)"
        rec = "Resultados" if x["esperada"] == "VRR" else (dest_ori if x["esperada"] == "VRORI" else "Solo revelación (NIIF 7 25)")
        nivel_txt = ("" if x["esperada"] not in ("VRR", "VRORI") else "Falta nivel" if x["nivel"] is None
                     else "Nivel 3: revisar supuestos (NIIF 13 86, 93)" if x["nivel"] == 3 else "Sí")
        vrz.append([x["id"], fx(f"{CLA}G{ri}", x["esperada"]), x["nivel"], x["vr"], fx(f"{INV}N{ri}", x["libros"]),
                    fx(f'IF(OR(B{r}="VRR",B{r}="VRORI"),IF(D{r}="","",D{r}-E{r}),"")', _v(x["difVR"])),
                    fx(f'IF(B{r}="VRR","Resultados",IF(B{r}="VRORI","{dest_ori}","Solo revelación (NIIF 7 25)"))', rec),
                    fx(f'IF(OR(B{r}="VRR",B{r}="VRORI"),IF(C{r}="","Falta nivel",IF(C{r}=3,"Nivel 3: revisar supuestos (NIIF 13 86, 93)","Sí")),"")', nivel_txt)])
    fin_vr = FILA0 + len(vrz) - 1

    ingresos, deterioro, concil = [], [], []
    for x in xs:
        r = fila[x["id"]]
        # 07
        if x["tipo"] == "Deuda" and x["id"] in fila_ca:
            f_esp = f'IF(OR(C{r}="CA",C{r}="VRORI"),{CAM}W{fila_ca[x["id"]]},"")'
        elif x["tipo"] == "Patrimonio":
            f_esp = f'IF({INV}S{r}="","",{INV}S{r})'
        else:
            f_esp = '""'
        ingresos.append([x["id"], fx(f'{INV}C{r}&""', x["tipo"]), fx(f"{CLA}G{r}", x["esperada"]), fx(f_esp, _v(x["ingEsp"])),
                         fx(f"{INV}R{r}", x["ingReg"] or 0.0), fx(f'IF(D{r}="","",D{r}-E{r})', _v(x["ingDif"]))])
        # 08
        ca_r = fila_ca.get(x["id"])
        if pymes:
            costo_k = f'IF({INV}K{r}="","",{INV}K{r})'
            base = f'IF(B{r}="CA",{CAM}Q{ca_r},IF(B{r}="COSTO",{costo_k},""))' if ca_r else f'IF(B{r}="COSTO",{costo_k},"")'
            enf = f'IF(OR(B{r}="CA",B{r}="COSTO"),IF(C{r}="Sí","Pérdida incurrida (11.21, 11.25)","Sin evidencia objetiva: sin pérdida (11.21)"),"No aplica")'
            calc = f'IF(OR(B{r}="CA",B{r}="COSTO"),IF(C{r}<>"Sí",0,IF(OR(E{r}="",G{r}=""),"",E{r}*G{r}/100)),"")'
        else:
            ap = f'OR(B{r}="CA",AND(B{r}="VRORI",{INV}C{r}="Deuda"))'
            base = f'IF({ap},{CAM}Q{ca_r},"")' if ca_r else '""'
            enf = f'IF({ap},IF(C{r}="Sí","Vida entera (5.5.3)","12 meses (5.5.5)"),"No aplica")'
            calc = f'IF({ap},IF(OR(E{r}="",F{r}="",G{r}=""),"",E{r}*F{r}/100*G{r}/100),"")'
        deterioro.append([x["id"], fx(f"{CLA}G{r}", x["esperada"]), x["indicio"], fx(enf, x["enfoque"]), fx(base, _v(x["base"])),
                          x["pd"], x["lgd"], fx(calc, _v(x["detCalc"])), fx(f"{INV}Q{r}", x["detReg"] or 0.0),
                          fx(f'IF(H{r}="","",H{r}-I{r})', _v(x["detDif"]))])
        # 10
        vr_r = fila_vr.get(x["id"])
        med_ca = f"{CAM}S{ca_r}" if ca_r else '""'
        med_vr = f'IF({VRZ}D{vr_r}="","",{VRZ}D{vr_r})' if vr_r else '""'
        f_med = f'IF(B{r}="CA",{med_ca},IF(OR(B{r}="VRR",B{r}="VRORI"),{med_vr},IF(B{r}="COSTO",IF({INV}K{r}="","",{INV}K{r}),"")))'
        concil.append([x["id"], fx(f"{CLA}G{r}", x["esperada"]), fx(f_med, _v(x["medicion"])), fx(f"{INV}N{r}", x["libros"]),
                       fx(f'IF(C{r}="","",C{r}-D{r})', _v(x["difMed"])), fx(f"{DET}H{r}", _v(x["detCalc"])), fx(f"{DET}I{r}", x["detReg"] or 0.0),
                       fx(f'IF(OR(B{r}="CA",B{r}="COSTO"),IF(F{r}="","",F{r}-G{r}),0)', _v(x["ajDet"])),
                       fx(f'IF(OR(E{r}="",H{r}=""),"",E{r}-H{r})', _v(x["ajuste"]))])
    fin = FILA0 + nx - 1

    recl = []
    for x in [y for y in xs if y["anterior"]]:
        r, ri = FILA0 + len(recl), fila[x["id"]]
        if pymes:
            f_perm = (f'IF(C{r}=D{r},"Sin cambio",IF(D{r}=F{r},"Sí: el instrumento cambió de condiciones (VERIFICAR soporte)",'
                      f'"No: la clasificación no corresponde a las condiciones del instrumento"))')
        else:
            f_perm = (f'IF(C{r}=D{r},"Sin cambio",IF(AND(B{r}="Patrimonio",C{r}="VRORI"),"No: elección irrevocable (5.7.5)",'
                      f'IF(AND(B{r}="Deuda",E{r}="Sí"),"Sí: cambio de modelo de negocio (4.4.1)","No: sin cambio de modelo de negocio (4.4.1)")))')
        recl.append([x["id"], fx(f'{INV}C{ri}&""', x["tipo"]), fx(f"{INV}X{ri}", x["anterior"]), fx(f"{INV}G{ri}", x["cliente"]),
                     x["cambio"], fx(f"{CLA}G{ri}", x["esperada"]), fx(f_perm, x["permitido"]), x["tratamiento"]])

    t = {k: float(v) for k, v in res["totals"].items()}
    tot_ref = {"saldoLibros": f"{CON}D{fin + 1}", "medicion": f"{CON}C{fin + 1}", "difMedicion": f"{CON}E{fin + 1}",
               "deterioroCalc": f"{DET}H{fin + 1}", "deterioroReg": f"{DET}I{fin + 1}", "ingresoDif": f"{ING}F{fin + 1}",
               "difVR": f"{VRZ}F{fin_vr + 1}" if vrz else "0", "ajuste": f"{CON}I{fin + 1}"}
    resumen = [[res["labels"][k], fx(tot_ref[k], n2(t[k]))] for k in res["labels"]]
    s = lambda col, fin_, k: suma(col, fin_, sum(x[k] for x in xs if x[k] is not None))
    sc = lambda col, k: suma(col, fin_ca, sum(x["ca"][k] for x in xs if x["ca"]))

    T = "t"
    return [
        hoja("01_Resumen", "Resumen", [["Concepto", T], ["Importe", "n"]], resumen),
        hoja("02_Parametros", "Parámetros", [["Parámetro", T], ["Valor", "x"], ["Sustento", T]], parametros),
        hoja("03_Inventario", "Inventario de inversiones",
             [["Instrumento", T], ["Emisor", T], ["Tipo", T], ["Modelo de negocio", T], ["SPPI / básico", T], ["Clasificación del cliente", T],
              ["Código cliente", T], ["Adquisición", "d"], ["Vencimiento", "d"], ["Nominal", "n"], ["Costo", "n"], ["Cupón %", "x"],
              ["Pagos por año", "i"], ["Saldo en libros", "n"], ["Valor razonable", "n"], ["Nivel", "i"], ["Deterioro registrado", "n"],
              ["Ingreso registrado", "n"], ["Dividendos decretados", "n"], ["Indicio", T], ["Calificación", T], ["PD %", "x"], ["LGD %", "x"],
              ["Clasificación anterior", T], ["Cambio de modelo", T]], inventario),
        hoja("04_Clasificacion", "Clasificación",
             [["Instrumento", T], ["Tipo", T], ["Modelo de negocio", T], ["SPPI / básico", T], ["Clasificación del cliente", T],
              ["¿VR medible?", T], ["Clasificación según la norma", T], ["¿Consistente?", T], ["Fundamento", T]], clasif),
        hoja("05_Costo_amortizado", "Costo amortizado y TIE",
             [["Instrumento", T], ["Adquisición", "d"], ["Vencimiento", "d"], ["Nominal", "n"], ["Costo", "n"], ["Cupón %", "x"],
              ["Pagos por año", "i"], ["Meses por período", "i"], ["Períodos totales", "i"], ["Cupón por período", "n"], ["TIE periódica", "p"],
              ["TIE anual", "p"], ["Control VA − costo", "n"], ["Cupones cobrados al corte", "i"], ["Fracción del período", "p"],
              ["CA al último cupón", "n"], ["CA al corte (con cupón corrido)", "n"], ["Cupón corrido", "n"], ["CA al corte (limpio)", "n"],
              ["Cupones cobrados al inicio", "i"], ["CA al inicio del ejercicio", "n"], ["Cupones cobrados en el ejercicio", "n"],
              ["Interés efectivo del ejercicio", "n"]], cam,
             ["TOTAL", "", "", suma("D", fin_ca, sum(x["nominal"] for x in xs if x["ca"])),
              suma("E", fin_ca, sum(x["costo"] for x in xs if x["ca"])), None, None, None, None, None, None, None, None, None, None, None,
              sc("Q", "sucio"), sc("R", "corrido"), sc("S", "limpio"), None, sc("U", "ini"), sc("V", "cupones"), sc("W", "interes")] if cam else None),
        hoja("06_Valor_razonable", "Valor razonable y jerarquía",
             [["Instrumento", T], ["Clasificación según la norma", T], ["Nivel", "i"], ["Valor razonable al corte", "n"], ["Saldo en libros", "n"],
              ["Diferencia (ganancia/pérdida no registrada)", "n"], ["Se reconoce en", T], ["¿Nivel informado?", T]], vrz,
             ["TOTAL", "", None, suma("D", fin_vr, sum(x["vr"] or 0 for x in xs if x["id"] in fila_vr)),
              suma("E", fin_vr, sum(x["libros"] for x in xs if x["id"] in fila_vr)),
              suma("F", fin_vr, sum(x["difVR"] or 0 for x in xs if x["id"] in fila_vr)), "", ""] if vrz else None),
        hoja("07_Intereses_dividendos", "Intereses y dividendos",
             [["Instrumento", T], ["Tipo", T], ["Clasificación según la norma", T], ["Ingreso según la norma", "n"], ["Ingreso registrado", "n"],
              ["Diferencia", "n"]], ingresos,
             ["TOTAL", "", "", s("D", fin, "ingEsp"), suma("E", fin, sum(x["ingReg"] or 0 for x in xs)), s("F", fin, "ingDif")]),
        hoja("08_Deterioro", "Deterioro",
             [["Instrumento", T], ["Clasificación según la norma", T], ["Indicio", T], ["Enfoque", T], ["Base (CA con cupón corrido / costo)", "n"],
              ["PD %", "x"], ["LGD / no recuperable %", "x"], ["Deterioro recalculado", "n"], ["Deterioro registrado", "n"], ["Diferencia", "n"]],
             deterioro, ["TOTAL", "", "", "", None, None, None, s("H", fin, "detCalc"), suma("I", fin, sum(x["detReg"] or 0 for x in xs)), s("J", fin, "detDif")]),
        hoja("09_Reclasificacion", "Reclasificación",
             [["Instrumento", T], ["Tipo", T], ["Clasificación anterior", T], ["Clasificación actual (cliente)", T], ["Cambio de modelo", T],
              ["Clasificación según la norma", T], ["¿Permitida?", T], ["Tratamiento", T]], recl),
        hoja("10_Conciliacion", "Conciliación y ajuste",
             [["Instrumento", T], ["Clasificación según la norma", T], ["Medición según la norma", "n"], ["Saldo en libros", "n"],
              ["Diferencia de medición", "n"], ["Deterioro recalculado", "n"], ["Deterioro registrado", "n"], ["Ajuste de deterioro", "n"],
              ["Ajuste propuesto (importe neto)", "n"]], concil,
             ["TOTAL", "", s("C", fin, "medicion"), s("D", fin, "libros"), s("E", fin, "difMed"), s("F", fin, "detCalc"),
              suma("G", fin, sum(x["detReg"] or 0 for x in xs)), s("H", fin, "ajDet"), s("I", fin, "ajuste")]),
        hoja("11_Problemas", "Problemas encontrados", [["Código", T], ["Descripción", T], ["Importe", "n"]],
             [[e["code"], e["message"], n2(e["amount"])] for e in res["exceptions"]]),
    ]


# --- definición ---------------------------------------------------------------------

def definicion() -> dict:
    anexo = ("Una fila por instrumento al corte: código, emisor, tipo, fechas de adquisición y vencimiento, nominal, costo, tasa cupón "
             "y pagos por año, modelo de negocio, ¿flujos solo principal e intereses?, clasificación del cliente, valor razonable y nivel, "
             "saldo en libros, intereses/dividendos registrados, dividendos decretados, deterioro registrado, calificación, indicio, PD y LGD, "
             "clasificación anterior y cambio de modelo. Sin filas de total.")
    return {
        "name": "Inversiones e instrumentos financieros",
        "area": "Inversiones",
        "processor": "inversiones_instrumentos",
        "frameworks": [MARCO_COMPLETAS, MARCO_PYMES],
        "summary": ("Clasifica cada inversión según el marco (NIIF 9: modelo de negocio y SPPI; PYMES: instrumento básico o no), recalcula "
                    "el costo amortizado con la tasa de interés efectiva, contrasta el valor razonable y su nivel de jerarquía, los intereses "
                    "y dividendos, el deterioro (pérdida esperada NIIF 9 / incurrida PYMES) y las reclasificaciones, y propone el ajuste."),
        "source": {"organization": "IFRS Foundation · Reglamento (UE) 2023/1803 (texto oficial en español)", "type": "Norma contable", "date": "",
                   "document": ("NIIF 9 párr. 4.1.1, 4.1.2, 4.1.2A, 4.1.4, 4.1.5, 4.4.1, 5.4.1, 5.5.1, 5.5.2, 5.5.3, 5.5.5, 5.5.17, "
                                "5.6.1–5.6.7, 5.7.1A, 5.7.5, 5.7.6, B5.7.1 y apéndice A (tipo de interés efectivo, fecha de reclasificación); "
                                "NIIF 13 párr. 72, 76, 81, 86, 93"),
                   "url": "https://eur-lex.europa.eu/legal-content/ES/TXT/HTML/?uri=CELEX:32023R1803"},
        "source_pymes": {"organization": "IFRS Foundation", "type": "Norma contable", "date": "",
                         "document": ("NIIF para las PYMES 2015: Secc. 11 párr. 11.8–11.9, 11.14, 11.15–11.20, 11.21–11.26, 11.27 (jerarquía); "
                                      "Secc. 12 párr. 12.8, 12.10. NIIF para las PYMES 2025 (3.ª ed.): Secc. 11 parte I 11.8, 11.9, 11.14, "
                                      "11.15–11.20, 11.21–11.26; parte II 11.14A, 11.49, 11.54, 11.55, 11.57; Secc. 12 Medición del valor razonable "
                                      "12.14–12.17 (técnicas) y 12.18–12.21 (medición fiable), 12.22–12.27 (leídos en los módulos educativos en inglés; texto oficial en español VERIFICAR)"),
                         "url": "https://www.ifrs.org/issued-standards/ifrs-for-smes/"},
        "nia": [
            {"document": "NIA 540 (Revisada)", "section": "párr. 13, 16–30 y 32",
             "requirement": "Valor razonable de nivel 2–3, TIE y pérdida esperada: evaluar método, datos y supuestos y el posible sesgo."},
            {"document": "NIA 500", "section": "párr. 6 y 9", "requirement": "Integridad y exactitud del anexo de inversiones contra el mayor."},
            {"document": "NIA 505", "section": "párr. 7", "requirement": "Confirmar existencia y tenencia con custodios, casas de valores o emisores."},
            {"document": "NIA 620", "section": "párr. 7", "requirement": "Uso de un experto para valoraciones de nivel 3 cuando corresponda."},
        ],
        "calculo": [
            "Clasificación esperada por marco: NIIF 9 con modelo de negocio y SPPI (4.1.1–4.1.5, 5.7.5); PYMES con instrumento básico (11.9), "
            "acciones con VR fiable (11.14 c) y el resto a VR con cambios en resultados (2015: 12.8; 2025: 11.54). PYMES no tiene VR con cambios en ORI.",
            "TIE periódica = TASA(períodos; cupón por período; −costo; nominal); control: VA de los flujos a la TIE − costo = 0.",
            "Costo amortizado al corte = VA de los flujos restantes a la TIE × (1 + TIE × fracción del período); costo amortizado limpio = menos el cupón corrido.",
            "Interés efectivo del ejercicio = costo amortizado final − inicial (o costo si se compró en el año) + cupones cobrados; contra lo registrado.",
            "Valor razonable: diferencia contra libros en VR con cambios en resultados (a resultados) o en ORI; nivel de jerarquía obligatorio (NIIF 13 72–90).",
            "Deterioro NIIF 9: exposición × PD × LGD (12 meses 5.5.5 / vida entera 5.5.3); PYMES: con evidencia objetiva, importe en libros × % no recuperable (11.25 a) costo amortizado; 11.25 b) costo menos deterioro).",
            "Reclasificación: solo por cambio de modelo (4.4.1) con el tratamiento 5.6.2–5.6.7; ORI de patrimonio irrevocable (5.7.5).",
            "Ajuste propuesto = (medición según la norma − saldo en libros) − (deterioro recalculado − registrado) en costo amortizado y costo.",
        ],
        "fields": _INVERSIONES, "rules": [], "control": CONTROL, "primary": "ajuste",
        "campos": CAMPOS, "tipos": TIPOS, "parametros": dict(PARAMETROS), "etiquetas_parametros": ETIQUETAS_PARAM,
        "cedulas": [[n, l] for n, l in CEDULAS],
        "program": [
            {"code": "INV-01", "objective": "Existencia e integridad", "risk": "Inversiones inexistentes o anexo no conciliado", "assertion": "Existencia",
             "procedure": "Conciliar el anexo por instrumento con el mayor y confirmar con custodios", "evidence": "Anexo, mayor, confirmaciones",
             "criterion": "Diferencias explicadas; tenencia confirmada", "source": "NIA 500 párr. 9 · NIA 505"},
            {"code": "INV-02", "objective": "Clasificación de instrumentos", "risk": "Categoría inconsistente con el modelo de negocio o el marco",
             "assertion": "Clasificación", "procedure": "Evaluar modelo de negocio y SPPI (NIIF 9) o instrumento básico (PYMES) y comparar con la clasificación del cliente",
             "evidence": "Políticas de inversión, actas, prospectos", "criterion": "Clasificación consistente con la norma",
             "source": "NIIF 9 4.1.1–4.1.5 · PYMES 11.8–11.9, 11.14"},
            {"code": "INV-03", "objective": "Costo amortizado", "risk": "Prima o descuento sin amortizar con la TIE", "assertion": "Valoración",
             "procedure": "Recalcular la TIE y el costo amortizado al corte", "evidence": "Prospectos, liquidaciones de compra",
             "criterion": "Diferencia cuantificada", "source": "NIIF 9 5.4.1, apéndice A · PYMES 11.15–11.20"},
            {"code": "INV-04", "objective": "Valor razonable", "risk": "Valor razonable sin sustento o sin nivel", "assertion": "Valoración",
             "procedure": "Contrastar precios de cierre o valoraciones y el nivel de jerarquía; recalcular la ganancia o pérdida",
             "evidence": "Vector de precios, bolsa, valuaciones", "criterion": "Diferencia contra libros evaluada",
             "source": "NIIF 13 72–90 · PYMES 2025 12.22–12.27 · PYMES 2015 11.27 · NIA 540"},
            {"code": "INV-05", "objective": "Intereses y dividendos", "risk": "Ingresos devengados no registrados o en exceso", "assertion": "Integridad",
             "procedure": "Recalcular interés efectivo y dividendos decretados y comparar con lo registrado", "evidence": "Estados de cuenta, actas de dividendos",
             "criterion": "Diferencia cuantificada", "source": "NIIF 9 5.4.1, 5.7.1A · PYMES 2025 11.14A y 11.55"},
            {"code": "INV-06", "objective": "Deterioro", "risk": "Pérdida esperada o incurrida no reconocida", "assertion": "Valoración",
             "procedure": "Evaluar indicios y calificaciones y recalcular el deterioro", "evidence": "Calificaciones de riesgo, información del emisor",
             "criterion": "Deterioro recalculado vs registrado", "source": "NIIF 9 5.5.1–5.5.5, 5.5.17 · PYMES 11.21–11.26"},
            {"code": "INV-07", "objective": "Reclasificación", "risk": "Reclasificación sin cambio de modelo de negocio", "assertion": "Presentación",
             "procedure": "Revisar cambios de categoría respecto del cierre anterior y su tratamiento", "evidence": "Actas del directorio, políticas",
             "criterion": "Solo por cambio de modelo, tratamiento 5.6", "source": "NIIF 9 4.4.1, 5.6.1–5.6.7, 5.7.5"},
        ],
        "requests": [
            req("RQ-001", "Anexo de inversiones por instrumento al corte", "inversiones", "INV-01", "Población a medir y conciliar con el mayor", content=anexo),
            req("RQ-002", "Estados de cuenta y confirmaciones de custodios o casas de valores", None, "INV-01", "Existencia y tenencia",
                formats=("pdf", "xlsx"), use="soporte"),
            req("RQ-003", "Política de inversiones y documentación del modelo de negocio (actas)", None, "INV-02", "Sustento de la clasificación",
                formats=("pdf", "docx"), use="soporte"),
            req("RQ-004", "Prospectos o contratos de los títulos (flujos contractuales)", None, "INV-03", "TIE y evaluación SPPI",
                formats=("pdf",), use="soporte"),
            req("RQ-005", "Precios de cierre, vector de precios o valuaciones", None, "INV-04", "Valor razonable y nivel de jerarquía",
                formats=("pdf", "xlsx"), use="soporte"),
            req("RQ-006", "Actas o avisos de dividendos decretados", None, "INV-05", "Dividendos con derecho establecido",
                formats=("pdf",), use="soporte", required=False),
            req("RQ-007", "Calificaciones de riesgo e información de los emisores", None, "INV-06", "Indicios de deterioro, PD y LGD",
                formats=("pdf", "xlsx"), use="soporte"),
        ],
    }


def validar_definicion(d: dict) -> dict:
    return validar_definicion_generica(d, DATASETS, PRINCIPAL)


# --- ejercicio modelo (M19) ------------------------------------------------------------

def _inv(id, emisor, tipo, clasificacion, saldo, **extra):
    return {"id": id, "emisor": emisor, "tipo": tipo, "clasificacion": clasificacion, "saldo_libros": saldo, "_row": 2, **extra}


# CDP-02: certificado a la par (50.000 al 6 % anual, compra 15-jul-2025): TIE = 6 %, costo amortizado
# limpio = 50.000; interés del ejercicio = 50.000 × 6 % × 169/365 = 1.389,04, nada registrado.
# ACC-04: valor razonable 45.000 (nivel 1) vs libros 42.000 → ganancia no registrada 3.000.
# PAG-07: pagaré con indicio de deterioro: 25.000 × (1 + 5 % × 92/181) × 60 % × 50 % = 7.690,61 vs 3.000 registrados.
EJEMPLO = {
    "corte": "2025-12-31",
    "parametros": {"frecuenciaDefecto": 1},
    "datasets": {"inversiones": [
        _inv("BONO-01", "Bonos del Estado (ficticio)", "Bono", "Costo amortizado", "96500", fecha_adq="2024-06-30", vence="2029-06-30",
             nominal="100000", costo="96000", cupon="8", frecuencia="2", modelo="Mantener para cobrar", sppi="Sí", ingreso_registrado="8000",
             calificacion="AA", indicio="No", pd="1", lgd="45", deterioro_registrado="0", valor_razonable="97200", nivel="2"),
        _inv("CDP-02", "Banco del Litoral (ficticio)", "Certificado de depósito", "Costo amortizado", "50000", fecha_adq="2025-07-15",
             vence="2026-07-15", nominal="50000", costo="50000", cupon="6", frecuencia="1", modelo="Mantener para cobrar", sppi="Sí",
             ingreso_registrado="0", calificacion="AAA", indicio="No", pd="0.5", lgd="40", deterioro_registrado="100"),
        _inv("OBL-03", "Industrial Andina (ficticio)", "Obligaciones", "Costo amortizado", "30400", fecha_adq="2024-03-31", vence="2027-03-31",
             nominal="30000", costo="30600", cupon="9", frecuencia="4", modelo="Cobrar y vender", sppi="Sí", valor_razonable="29400", nivel="2",
             ingreso_registrado="2500", calificacion="A", indicio="No", pd="1", lgd="45"),
        _inv("ACC-04", "Comercial Andina (ficticio)", "Acciones", "VR con cambios en resultados", "42000", modelo="Negociar", costo="40000",
             valor_razonable="45000", nivel="1", dividendos="1800", ingreso_registrado="1800"),
        _inv("ACC-05", "Inmobiliaria Sur (ficticio)", "Acciones", "VR con cambios en ORI", "12500", modelo="Mantener", costo="10000",
             valor_razonable="12500", nivel="3", dividendos="500", ingreso_registrado="0"),
        _inv("FND-06", "Fondo Renta Fija (ficticio)", "Fondo de inversión", "VR con cambios en resultados", "20000", modelo="Negociar",
             costo="19000", valor_razonable="20500", ingreso_registrado="0"),
        _inv("PAG-07", "Distribuidora Norte (ficticio)", "Pagaré", "Costo amortizado", "25000", fecha_adq="2024-09-30", vence="2026-09-30",
             nominal="25000", costo="25000", cupon="10", frecuencia="2", modelo="Mantener para cobrar", sppi="Sí", ingreso_registrado="2500",
             calificacion="C", indicio="Sí", pd="60", lgd="50", deterioro_registrado="3000"),
        _inv("BONO-08", "Energía Convertible (ficticio)", "Bono convertible", "Costo amortizado", "15000", fecha_adq="2025-01-31",
             vence="2028-01-31", nominal="15000", costo="15000", cupon="5", frecuencia="1", modelo="Mantener para cobrar", sppi="No",
             valor_razonable="15800", nivel="2", ingreso_registrado="687.50"),
        _inv("POL-09", "Financiera Pacífico (ficticio)", "Póliza de acumulación", "Costo amortizado", "9800", fecha_adq="2025-10-31",
             vence="2026-04-30", nominal="10000", costo="9800", cupon="0", frecuencia="2", modelo="Mantener para cobrar", sppi="Sí",
             ingreso_registrado="0", calificacion="BB", indicio="No", pd="2", lgd="40"),
        _inv("OBL-10", "Eléctrica Costa (ficticio)", "Obligaciones", "VR con cambios en ORI", "20200", fecha_adq="2023-12-31",
             vence="2028-12-31", nominal="20000", costo="20000", cupon="8", frecuencia="1", modelo="Cobrar y vender", sppi="Sí",
             valor_razonable="20200", nivel="2", ingreso_registrado="1600", calificacion="A", indicio="No", pd="1.5", lgd="45",
             deterioro_registrado="0", clasificacion_anterior="Costo amortizado", cambio_modelo="No"),
        _inv("BONO-11", "Constructora Sierra (ficticio)", "Bono", "Costo amortizado", "5000", fecha_adq="2023-11-30", vence="2025-11-30",
             nominal="5000", costo="5000", cupon="7", frecuencia="1", modelo="Mantener para cobrar", sppi="Sí", ingreso_registrado="350"),
    ]},
}

ESCENARIOS = [
    ("niif_completas", EJEMPLO["datasets"], EJEMPLO["parametros"], EJEMPLO["corte"]),
    ("pymes_2015", EJEMPLO["datasets"], {**EJEMPLO["parametros"], "_marco": MARCO_PYMES, "_edicion": "2015"}, EJEMPLO["corte"]),
    ("pymes_2025", EJEMPLO["datasets"], {**EJEMPLO["parametros"], "_marco": MARCO_PYMES, "_edicion": "2025"}, EJEMPLO["corte"]),
]
