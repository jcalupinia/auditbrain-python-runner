"""Pérdida crediticia esperada de cuentas por cobrar comerciales, enfoque
simplificado de la NIIF 9 (párr. 5.5.15) con matriz de provisiones (B5.5.35).

Versión simple que cumple la norma:

1. Tramo de mora de cada factura al corte (corriente, 1–30, 31–60, 61–90,
   91–180, 181–360, más de 360) y segmento opcional (B5.5.35: agrupar si los
   segmentos pierden distinto).
2. Tasa histórica por segmento y tramo con la cartera del corte anterior: lo que
   un año después sigue impago (en impago: más de 90 días, B5.5.37) o fue
   castigado (5.4.4), ÷ el saldo inicial del tramo. Solo saldos positivos.
3. Si un tramo no tiene historia, el auditor fija la tasa: nunca queda en cero
   por omisión (la pérdida esperada existe aunque no haya evento de pérdida).
4. Ajuste prospectivo (5.5.17 c, B5.5.52): factor ponderado de tres escenarios.
5. Pérdida esperada por factura = saldo × tasa ajustada ÷ (1 + i)^(plazo/12)
   (5.5.17 b; i = 0 en cartera de corto plazo). Tasa individual opcional por
   factura con evidencia específica.
6. Ajuste contra la provisión registrada; movimiento (NIIF 7 35H); matriz para
   las notas (NIIF 7 35M/35N); límites LRTI e impuesto diferido; asientos.

El libro Excel lleva cada importe como fórmula que remite a Parámetros, Cartera
anterior, Castigos, Tasas históricas, Matriz y Detalle.
"""
from __future__ import annotations

from datetime import date

from backend.app.aud.niif.procesadores import problemas
from backend.app.aud.niif.procesadores.perdidas_incurridas_s11 import (
    FILA0, _fx, _m, _n, a_fecha, a_num, filas_mapeadas, r2,
)

VERSION = "pce-simplificada 1.0"

TRAMOS = [
    {"k": "pv", "n": "Corriente / por vencer", "min": float("-inf"), "max": 0},
    {"k": "t30", "n": "1 a 30 días", "min": 1, "max": 30},
    {"k": "t60", "n": "31 a 60 días", "min": 31, "max": 60},
    {"k": "t90", "n": "61 a 90 días", "min": 61, "max": 90},
    {"k": "t180", "n": "91 a 180 días", "min": 91, "max": 180},
    {"k": "t360", "n": "181 a 360 días", "min": 181, "max": 360},
    {"k": "tmax", "n": "Más de 360 días", "min": 361, "max": float("inf")},
]
NOMBRE_TRAMO = {t["k"]: t["n"] for t in TRAMOS}
IMPAGO_DIAS = 90  # B5.5.37: presunción de impago a los 90 días de mora

_CARTERA = [
    {"key": "id", "label": "N° de factura", "type": "text", "required": True,
     "aliases": ["numfac", "factura", "documento", "comprobante", "numero de factura", "nro factura"]},
    {"key": "cliente", "label": "Cliente", "type": "text", "required": True,
     "aliases": ["nomcli", "razon social", "nombre del cliente", "deudor", "nombre"]},
    {"key": "vence", "label": "Fecha de vencimiento", "type": "date", "required": True,
     "aliases": ["vence", "vencimiento", "fecha vencimiento", "fecvto"]},
    {"key": "saldo", "label": "Saldo por cobrar", "type": "number", "required": True,
     "aliases": ["saldo", "saldo pendiente", "por cobrar", "pendiente", "saldo actual"]},
    {"key": "segmento", "label": "Segmento (opcional)", "type": "text", "required": False,
     "aliases": ["segmento", "tipo de cliente", "region", "canal", "grupo"]},
    {"key": "tasa_individual", "label": "Tasa individual % (opcional)", "type": "number", "required": False,
     "aliases": ["tasa individual", "tasa especifica", "evaluacion individual"]},
    {"key": "ruc", "label": "RUC / identificación", "type": "text", "required": False,
     "aliases": ["ruc", "cedula", "identificacion", "codigo cliente"]},
]
CAMPOS = {
    "cartera": _CARTERA,
    "castigos": [
        {"key": "id", "label": "N° de factura", "type": "text", "required": True,
         "aliases": ["numfac", "factura", "documento", "comprobante", "numero de factura"]},
        {"key": "cliente", "label": "Cliente", "type": "text", "required": True,
         "aliases": ["nomcli", "razon social", "nombre del cliente", "deudor", "nombre"]},
        {"key": "importe", "label": "Importe castigado", "type": "number", "required": True,
         "aliases": ["importe", "castigo", "valor castigado", "monto"]},
    ],
}
TIPOS = {"actual": "cartera", "anterior": "cartera", "castigos": "castigos"}
DATASETS = tuple(TIPOS)

PARAMETROS = {
    "tasaDesc": 0, "plazoBase": 12,
    "escBasePeso": 100, "escBaseAjuste": 0, "escOptPeso": 0, "escOptAjuste": 0, "escPesPeso": 0, "escPesAjuste": 0,
    "provisionRegistrada": None, "provisionInicial": None,
    "pctDeducible": 1, "pctLimite": 10, "tasaImp": 25, "provFiscalAnt": None, "tasas": {},
}
# Los ajustes de escenario pueden ser negativos (escenario optimista).
PARAM_NEGATIVOS = ("escBaseAjuste", "escOptAjuste", "escPesAjuste")
ETIQUETAS_PARAM = {
    "tasaDesc": "Tasa efectiva (%)", "plazoBase": "Plazo de cobro (meses)",
    "escBasePeso": "Escenario base: peso %", "escBaseAjuste": "Escenario base: ajuste %",
    "escOptPeso": "Optimista: peso %", "escOptAjuste": "Optimista: ajuste %",
    "escPesPeso": "Pesimista: peso %", "escPesAjuste": "Pesimista: ajuste %",
    "provisionRegistrada": "Provisión registrada al cierre (mayor)", "provisionInicial": "Provisión al inicio del año",
    "pctDeducible": "Límite anual (%)", "pctLimite": "Límite acumulado (%)", "tasaImp": "Tasa del impuesto (%)",
    "provFiscalAnt": "Provisión fiscal anterior",
}


# Total que muestra el ejemplo de control en el Estudio.
TOTAL_EJEMPLO = "pce"
# Anexo que es la población del corte (se concilia con el mayor).
PRINCIPAL = "actual"


def kind(dataset: str) -> str:
    return TIPOS[dataset]


def validar_filas(tipo: str, filas: list) -> dict:
    """Faltantes, números y fechas ilegibles, filas de total y facturas repetidas."""
    import re

    errores, avisos, vistos = [], [], {}
    for f in filas:
        fila = f.get("_row")
        for c in CAMPOS[tipo]:
            v = str(f.get(c["key"], "") or "").strip()
            if c.get("required") and not v:
                errores.append({"row": fila, "field": c["key"], "message": f"Falta {c['label']}."})
            elif v and c["type"] == "number" and a_num(v) is None:
                errores.append({"row": fila, "field": c["key"], "message": f"{c['label']}: número inválido."})
            elif v and c["type"] == "date" and a_fecha(v) is None:
                errores.append({"row": fila, "field": c["key"], "message": f"{c['label']}: fecha inválida."})
        if re.match(r"^(total|subtotal)\b", str(f.get("id", "")), re.I):
            errores.append({"row": fila, "message": "Fila de total o subtotal: prepare un anexo de detalle."})
        ti = str(f.get("tasa_individual", "") or "").strip()
        if ti and a_num(ti) is not None and not 0 <= a_num(ti) <= 100:
            errores.append({"row": fila, "field": "tasa_individual", "message": "Tasa individual: use un porcentaje entre 0 y 100."})
        k = str(f.get("id", "")).strip().lower()
        if tipo == "cartera" and k:
            if k in vistos:
                avisos.append({"row": fila, "message": f"Factura repetida: {f.get('id')} (también en la fila {vistos[k]})."})
            vistos.setdefault(k, fila)
    return {"records": len(filas), "errors": errores, "warnings": avisos, "ok": not errores}


# --- cálculo -----------------------------------------------------------------

def _clave(v) -> str:
    """Igual que SUMIF de Excel: sin espacios de borde y sin distinguir mayúsculas."""
    return str(v if v is not None else "").strip().lower()


def _tramo(dv):
    return next(t for t in TRAMOS if t["min"] <= dv <= t["max"]) if dv is not None else None


def _hace_un_anio(d: date) -> date:
    try:
        return d.replace(year=d.year - 1)
    except ValueError:  # 29 de febrero
        return d.replace(year=d.year - 1, day=28)


def _cartera(filas: list, corte: date) -> list:
    out = []
    for f in filas or []:
        saldo = a_num(f.get("saldo"))
        if saldo is None or saldo == 0:
            continue
        vence = a_fecha(f.get("vence"))
        dv = (corte - vence).days if vence else None
        t = _tramo(dv)
        seg = str(f.get("segmento", "") or "").strip() or "General"
        ti = a_num(f.get("tasa_individual")) if str(f.get("tasa_individual", "") or "").strip() else None
        out.append({"factura": str(f.get("id", "")).strip(), "cliente": str(f.get("cliente", "")).strip() or "(sin nombre)",
                    "vence": vence, "dv": dv, "tramo": t["k"] if t else None, "segmento": seg, "saldo": saldo,
                    "tasaInd": ti, "ruc": str(f.get("ruc", "") or "").strip(), "_row": f.get("_row")})
    return out


def ejecutar(datasets: dict, parametros: dict, corte: str) -> dict:
    p = {**PARAMETROS, **{k: v for k, v in (parametros or {}).items() if v is not None and v != ""}}
    corte_a = a_fecha(corte)
    if corte_a is None:
        raise ValueError("Indique la fecha de corte del encargo.")
    corte_b = _hace_un_anio(corte_a)
    actual = _cartera(datasets.get("actual"), corte_a)
    if not actual:
        raise ValueError("Cargue la cartera por factura al corte del ejercicio.")
    anterior = [f for f in _cartera(datasets.get("anterior"), corte_b) if f["saldo"] > 0]
    castigos = {}
    for c in datasets.get("castigos") or []:
        k = _clave(c.get("id"))
        castigos[k] = castigos.get(k, 0) + (a_num(c.get("importe")) or 0)
    total_castigos = sum(castigos.values())

    # 2 · historia: lo que sigue impago o fue castigado ÷ saldo inicial del tramo.
    saldo_act = {}
    for f in actual:
        saldo_act[_clave(f["factura"])] = saldo_act.get(_clave(f["factura"]), 0) + f["saldo"]
    for f in anterior:
        f["sigue"] = max(0, min(saldo_act.get(_clave(f["factura"]), 0), f["saldo"]))
        f["castigado"] = max(0, min(castigos.get(_clave(f["factura"]), 0), f["saldo"] - f["sigue"]))
        f["perdida"] = f["sigue"] + f["castigado"]
    historia = {}
    for f in anterior:
        h = historia.setdefault((f["segmento"], f["tramo"]), {"inicial": 0, "perdida": 0, "docs": 0})
        h["inicial"] += f["saldo"]
        h["perdida"] += f["perdida"]
        h["docs"] += 1

    # 3–4 · tasa por segmento y tramo, fijada por el auditor si falta, y ajuste prospectivo.
    pesos = [(float(p["escBasePeso"]), float(p["escBaseAjuste"])), (float(p["escOptPeso"]), float(p["escOptAjuste"])),
             (float(p["escPesPeso"]), float(p["escPesAjuste"]))]
    suma = sum(w for w, _ in pesos)
    if suma <= 0:
        raise ValueError("Los pesos de los escenarios deben sumar más de cero.")
    factor = sum(w * (1 + a / 100) for w, a in pesos) / suma
    manual = {k: float(a_num(v)) for k, v in (p.get("tasas") or {}).items() if a_num(v) is not None}
    segmentos = sorted({f["segmento"] for f in actual} | {f["segmento"] for f in anterior})
    matriz = []
    for s in segmentos:
        for t in TRAMOS:
            h = historia.get((s, t["k"]))
            hist = h["perdida"] / h["inicial"] if h and h["inicial"] > 0 else None
            man = manual.get(t["k"])
            base = hist if hist is not None else (man / 100 if man is not None else None)
            matriz.append({"segmento": s, "k": t["k"], "tramo": t["n"], "clave": f"{s}|{t['n']}", "inicial": h["inicial"] if h else 0,
                           "perdidaHist": h["perdida"] if h else 0, "docsHist": h["docs"] if h else 0, "hist": hist, "manual": man,
                           "base": base, "ajustada": None if base is None else min(base * factor, 1)})
    tasa_de = {m["clave"]: m["ajustada"] for m in matriz}

    # 5 · pérdida esperada por factura.
    desc = (1 + float(p["tasaDesc"]) / 100) ** (float(p["plazoBase"]) / 12)
    for f in actual:
        f["clave"] = f"{f['segmento']}|{NOMBRE_TRAMO.get(f['tramo'], '')}"
        f["tasa"] = f["tasaInd"] / 100 if f["tasaInd"] is not None else tasa_de.get(f["clave"])
        f["pce"] = None if f["tasa"] is None else max(f["saldo"] * f["tasa"] / desc, 0)
    for m in matriz:
        m["saldo"] = sum(f["saldo"] for f in actual if f["clave"] == m["clave"])
        m["pce"] = sum(f["pce"] or 0 for f in actual if f["clave"] == m["clave"])
        m["docs"] = sum(1 for f in actual if f["clave"] == m["clave"])
        m["sinTasa"] = sum(f["saldo"] for f in actual if f["clave"] == m["clave"] and f["tasa"] is None)
    total = sum(f["saldo"] for f in actual)
    pce = sum(f["pce"] or 0 for f in actual)
    prov_reg = a_num(p.get("provisionRegistrada")) if p.get("provisionRegistrada") is not None else None
    prov_ini = a_num(p.get("provisionInicial")) if p.get("provisionInicial") is not None else 0.0

    # 6 · movimiento (NIIF 7 35H), fiscal y diferido.
    dotacion = pce - prov_ini + total_castigos
    corriente = sum(f["saldo"] for f in actual if f["dv"] is not None and f["dv"] <= 0)
    lim1 = corriente * float(p["pctDeducible"]) / 100
    lim10 = total * float(p["pctLimite"]) / 100
    pf_estimada = p.get("provFiscalAnt") is None
    pf_ant = min(prov_ini, lim10) if pf_estimada else float(a_num(p["provFiscalAnt"]))
    margen = max(lim10 - pf_ant, 0)
    deducible = max(min(max(dotacion, 0), lim1, margen), 0)
    no_ded = max(max(dotacion, 0) - deducible, 0)
    pf_acum = pf_ant + deducible
    ti = float(p["tasaImp"]) / 100
    dif = max(pce - pf_acum, 0)
    dta_fin = dif * ti
    dta_ini = max(prov_ini - pf_ant, 0) * ti
    fiscal = {"total": total, "corriente": corriente, "pce": pce, "provIni": prov_ini, "castigos": total_castigos,
              "dotacion": dotacion, "limite1": lim1, "limite10": lim10, "provFiscalAnt": pf_ant, "pfEstimada": pf_estimada,
              "margen": margen, "deducible": deducible, "noDeducible": no_ded, "provFiscalAcum": pf_acum, "dif": dif,
              "dtaFin": dta_fin, "dtaIni": dta_ini, "dtaMov": dta_fin - dta_ini}

    asientos = []
    if dotacion > 0.005:
        asientos.append({"n": "1", "titulo": "Pérdida crediticia esperada del ejercicio", "ref": "dotacion", "lineas": [
            {"cta": "Gasto por pérdidas crediticias esperadas", "d": dotacion}, {"cta": "(-) Provisión por pérdidas crediticias esperadas", "h": dotacion}]})
    elif dotacion < -0.005:
        asientos.append({"n": "1", "titulo": "Reversión de pérdidas crediticias esperadas", "ref": "dotacion", "lineas": [
            {"cta": "(-) Provisión por pérdidas crediticias esperadas", "d": -dotacion}, {"cta": "Ingreso por reversión de pérdidas crediticias esperadas", "h": -dotacion}]})
    if total_castigos > 0.005:
        asientos.append({"n": "2", "titulo": "Castigos del ejercicio (5.4.4)", "ref": "castigos", "lineas": [
            {"cta": "(-) Provisión por pérdidas crediticias esperadas", "d": total_castigos}, {"cta": "Cuentas por cobrar comerciales", "h": total_castigos}]})
    if abs(dta_fin - dta_ini) > 0.005:
        mov = dta_fin - dta_ini
        asientos.append({"n": "3", "titulo": "Activo por impuesto diferido", "ref": "dtaMov", "lineas": (
            [{"cta": "Activo por impuesto diferido", "d": mov}, {"cta": "Ingreso por impuesto a la renta diferido", "h": mov}] if mov > 0 else
            [{"cta": "Gasto por impuesto a la renta diferido", "d": -mov}, {"cta": "Activo por impuesto diferido", "h": -mov}])})

    problemas = []
    for m in matriz:
        if m["ajustada"] is None and m["sinTasa"]:
            problemas.append({"code": "TASA_FALTANTE", "message": f"{m['segmento']} · {m['tramo']}: sin historia ({_m(m['sinTasa'])} de cartera sin tasa). Fije la tasa con su sustento (B5.5.51).", "amount": r2(m["sinTasa"])})
    for m in matriz:
        if m["ajustada"] == 0 and m["saldo"] > 0:
            problemas.append({"code": "TASA_CERO", "message": f"{m['segmento']} · {m['tramo']}: tasa 0 % sobre {_m(m['saldo'])}. La pérdida esperada se estima aunque la posibilidad sea muy baja (5.5.18): documente por qué es cero o fije una tasa.", "amount": r2(m["saldo"])})
    for s in segmentos:
        tasas = [m["ajustada"] for m in matriz if m["segmento"] == s and m["ajustada"] is not None and m["docs"]]
        if any(b < a - 1e-9 for a, b in zip(tasas, tasas[1:])):
            problemas.append({"code": "TASAS_NO_CRECIENTES", "message": f"{s}: la tasa baja en algún tramo más antiguo; revise la historia o documente la causa.", "amount": "0.00"})
    if not anterior:
        problemas.append({"code": "SIN_HISTORIA", "message": "No se cargó la cartera del corte anterior: todas las tasas deben fijarse con sustento.", "amount": "0.00"})
    if abs(factor - 1) < 1e-9:
        problemas.append({"code": "SIN_AJUSTE_PROSPECTIVO", "message": "Factor prospectivo 1,00: documente por qué las condiciones actuales y previstas no cambian la historia (5.5.17 c, B5.5.52).", "amount": "0.00"})
    if prov_reg is None:
        problemas.append({"code": "SIN_PROVISION_REGISTRADA", "message": "Ingrese la provisión registrada según el mayor para medir el ajuste.", "amount": "0.00"})
    elif abs(pce - prov_reg) > 0.005:
        problemas.append({"code": "AJUSTE", "message": f"La pérdida esperada ({_m(pce)}) difiere de la provisión registrada ({_m(prov_reg)}).", "amount": r2(pce - prov_reg)})
    impago = sum(f["saldo"] for f in actual if f["dv"] is not None and f["dv"] > IMPAGO_DIAS)
    if impago > 0:
        problemas.append({"code": "EN_IMPAGO", "message": f"Cartera en impago (más de {IMPAGO_DIAS} días, B5.5.37): {_m(impago)}. Evalúe castigo (5.4.4) o tasa individual.", "amount": r2(impago)})
    if no_ded > 0.005:
        problemas.append({"code": "NO_DEDUCIBLE", "message": f"Gasto no deducible del ejercicio: {_m(no_ded)} (límites LRTI).", "amount": r2(no_ded)})

    filas = [{"id": f["factura"], "cliente": f["cliente"], "segmento": f["segmento"], "vence": f["vence"].isoformat() if f["vence"] else "",
              "dias": "" if f["dv"] is None else str(f["dv"]), "tramo": NOMBRE_TRAMO.get(f["tramo"], "—"), "saldo": r2(f["saldo"]),
              "tasaInd": "" if f["tasaInd"] is None else str(f["tasaInd"]), "tasa": "" if f["tasa"] is None else f"{f['tasa']:.6f}",
              "pce": "" if f["pce"] is None else r2(f["pce"]), "_row": f["_row"]} for f in actual]
    totales = {"saldo": r2(total), "pce": r2(pce), "provisionRegistrada": r2(prov_reg or 0), "ajuste": r2(pce - (prov_reg or 0)),
               "dotacion": r2(dotacion), "castigos": r2(total_castigos), "deducible": r2(deducible), "noDeducible": r2(no_ded),
               "dtaFin": r2(dta_fin), "dtaMov": r2(dta_fin - dta_ini)}
    etiquetas = {"saldo": "Cartera al corte", "pce": "Pérdida crediticia esperada", "provisionRegistrada": "Provisión registrada (mayor)",
                 "ajuste": "Ajuste propuesto", "dotacion": "Dotación neta del ejercicio", "castigos": "Castigos del ejercicio",
                 "deducible": "Gasto deducible", "noDeducible": "Gasto no deducible", "dtaFin": "Activo por impuesto diferido",
                 "dtaMov": "Movimiento del diferido"}
    detalle = {"cortes": {"actual": corte_a.isoformat(), "anterior": corte_b.isoformat()}, "factor": factor, "matriz": matriz,
               "tasas": [{"k": t["k"], "tramo": t["n"], "tasa": next((m["ajustada"] for m in matriz if m["k"] == t["k"] and m["ajustada"] is not None), None),
                          "origen": "Historia × factor prospectivo" if any(m["hist"] is not None for m in matriz if m["k"] == t["k"]) else ("Fijada por el auditor" if t["k"] in manual else "Sin tasa")} for t in TRAMOS],
               "anterior": [{k: (v.isoformat() if isinstance(v, date) else v) for k, v in f.items()} for f in anterior],
               "castigos": [{"id": c.get("id"), "cliente": c.get("cliente"), "importe": a_num(c.get("importe")) or 0} for c in datasets.get("castigos") or []],
               "fiscal": fiscal, "asientos": asientos, "parametros": p, "provisionRegistrada": prov_reg}
    return {"engine": VERSION, "rows": filas, "totals": totales, "labels": etiquetas, "primary": "ajuste",
            "exceptions": problemas, "schedule": [], "detalle": detalle}


# --- cédulas con fórmulas ---------------------------------------------------------

CEDULAS = [
    ("01_Resumen", "Resumen"), ("02_Parametros", "Parámetros"), ("03_Tasas_historicas", "Tasas históricas"),
    ("04_Matriz_provisiones", "Matriz de provisiones"), ("05_Revelacion_NIIF7", "Revelación NIIF 7 (35M/35N)"),
    ("06_Movimiento", "Movimiento de la provisión (NIIF 7 35H)"), ("07_Fiscal", "Fiscal e impuesto diferido"),
    ("08_Asientos", "Asientos propuestos"), ("09_Detalle", "Detalle por factura"), ("10_Cartera_anterior", "Cartera del corte anterior"),
    ("11_Castigos", "Castigos del ejercicio"), ("12_Problemas", "Problemas encontrados"),
]
P = "'02_Parametros'!"
PAR = {k: FILA0 + i for i, k in enumerate(["corte", "corteAnterior", "tasaDesc", "plazoBase", "escBasePeso", "escBaseAjuste",
                                            "escOptPeso", "escOptAjuste", "escPesPeso", "escPesAjuste", "factor",
                                            "provisionRegistrada", "provisionInicial", "pctDeducible", "pctLimite", "tasaImp", "provFiscalAnt"])}
DET, ANT, CAS, HIS, MAT, FIS = "'09_Detalle'!", "'10_Cartera_anterior'!", "'11_Castigos'!", "'03_Tasas_historicas'!", "'04_Matriz_provisiones'!", "'07_Fiscal'!"
FISC = ["total", "corriente", "pce", "provIni", "castigos", "dotacion", "limite1", "limite10", "provFiscalAnt", "margen",
        "deducible", "noDeducible", "provFiscalAcum", "dif", "dtaFin", "dtaIni", "dtaMov"]
F_ = {k: f"{FIS}$B${FILA0 + i}" for i, k in enumerate(FISC)}


# Explicación humana de cada columna calculada («Cómo se calcula esta hoja»).
EXPLICA = {
    "01_Resumen": {
        "Importe": ("Trae cada importe de la hoja donde se calculó: cartera, pérdida esperada, dotación, castigos, gasto "
                    "deducible y no deducible y diferido de la hoja 07 (Fiscal e impuesto diferido); la provisión "
                    "registrada de la hoja 02 (Parámetros). El ajuste propuesto es la pérdida esperada menos la provisión registrada."),
    },
    "02_Parametros": {
        "Valor": ("Los parámetros son datos del encargo o juicio del auditor; solo el factor prospectivo ponderado se "
                  "calcula: suma peso × (1 + ajuste) de los tres escenarios y lo divide para la suma de los pesos."),
    },
    "03_Tasas_historicas": {
        "Facturas": ("Cuenta cuántas facturas de la cartera del corte anterior (hoja 10) tienen este mismo segmento y "
                     "tramo de mora."),
        "Saldo al corte anterior": ("Suma el saldo que tenían, al corte anterior, las facturas de este segmento y tramo en "
                                    "la hoja 10 (Cartera del corte anterior)."),
        "Impago o castigado un año después": ("Suma la pérdida observada de esas mismas facturas en la hoja 10: lo que un "
                                              "año después seguía impago más lo que se castigó."),
        "Tasa histórica": ("Divide lo impago o castigado un año después para el saldo al corte anterior: es la tasa de "
                           "pérdida que mostró la historia. Si no hubo saldo anterior, queda en blanco."),
    },
    "04_Matriz_provisiones": {
        "Tasa histórica": "Trae la tasa histórica del mismo segmento y tramo desde la hoja 03 (Tasas históricas).",
        "Tasa fijada": ("Solo si el auditor fijó una tasa para el tramo: la toma de la hoja 02 (Parámetros) y la divide "
                        "para 100. Si no la fijó, queda en blanco."),
        "Tasa base": ("Usa la tasa histórica si existe; si no hay historia, usa la tasa fijada por el auditor; si no hay "
                      "ninguna de las dos, queda en blanco."),
        "Factor prospectivo": ("Trae el factor prospectivo ponderado de la hoja 02 (Parámetros), que ajusta la historia "
                               "con los escenarios base, optimista y pesimista."),
        "Tasa aplicada": ("Multiplica la tasa base por el factor prospectivo, con un tope de 100 %. Si el tramo no tiene "
                          "tasa base, queda en blanco."),
        "Saldo al corte": ("Suma el saldo de las facturas del detalle (hoja 09) que tienen este mismo segmento y tramo "
                           "de mora."),
        "Pérdida esperada": ("Suma la pérdida esperada calculada factura por factura en la hoja 09 (Detalle por factura) "
                             "para este segmento y tramo."),
    },
    "05_Revelacion_NIIF7": {
        "Importe en libros bruto": ("Suma el saldo de todas las facturas del detalle (hoja 09) que caen en este tramo de "
                                    "mora, sin importar el segmento."),
        "Tasa esperada promedio": ("Divide la pérdida esperada del tramo para su importe en libros bruto: es la tasa "
                                   "promedio del tramo. Si el tramo no tiene saldo, queda en blanco."),
        "Pérdida esperada": ("Suma la pérdida esperada de todas las facturas del detalle (hoja 09) que caen en este "
                             "tramo de mora, de todos los segmentos."),
    },
    "06_Movimiento": {
        "Importe": ("Trae la provisión inicial, los castigos y la dotación neta de la hoja 07 (Fiscal e impuesto "
                    "diferido); la última fila parte de la provisión inicial, resta los castigos y suma la dotación, y "
                    "debe igualar la pérdida esperada al cierre."),
    },
    "07_Fiscal": {
        "Importe": ("Cada concepto tiene su propio cálculo: cartera, parte corriente y pérdida esperada se suman del "
                    "detalle (hoja 09); la provisión inicial viene de la hoja 02 (Parámetros) y los castigos de la hoja "
                    "11; la dotación es pérdida esperada − provisión inicial + castigos; los límites y el diferido aplican "
                    "los porcentajes de la hoja 02; el resto combina las filas anteriores de esta hoja."),
    },
    "08_Asientos": {
        "Debe": ("Toma el importe del asiento de la hoja 07 (Fiscal e impuesto diferido): la dotación neta y el "
                 "movimiento del diferido en valor absoluto, y los castigos del ejercicio."),
        "Haber": ("Lleva a la contrapartida el mismo importe del asiento, tomado de la hoja 07 (Fiscal e impuesto "
                  "diferido), para que debe y haber cuadren."),
    },
    "09_Detalle": {
        "Días de mora": ("Resta la fecha de vencimiento de la fecha de corte de la hoja 02 (Parámetros); si la factura no "
                         "tiene vencimiento, queda en blanco. Cero o negativo significa que aún no vence."),
        "Tramo": ("Clasifica la factura por sus días de mora: corriente/por vencer si no tiene mora, luego 1 a 30, 31 a 60, "
                  "61 a 90, 91 a 180, 181 a 360 y más de 360 días. Sin días de mora queda en blanco."),
        "Clave": ("Une el segmento y el tramo de la factura (segmento|tramo) para buscar su tasa en la hoja 04 (Matriz "
                  "de provisiones)."),
        "Tasa aplicada": ("Si la factura tiene tasa individual, usa esa tasa dividida para 100; si no, busca la tasa "
                          "aplicada de su segmento y tramo en la hoja 04 (Matriz de provisiones). Si no la encuentra o "
                          "está vacía, queda en blanco."),
        "Pérdida esperada": ("Multiplica el saldo por la tasa aplicada y lo descuenta con la tasa y el plazo de cobro de la "
                             "hoja 02 (Parámetros); nunca es negativa. Sin tasa, queda en blanco."),
        "En impago": ("Marca «Sí» si la factura tiene más de 90 días de mora y «No» en caso contrario; sin días de mora "
                      "queda en blanco."),
    },
    "10_Cartera_anterior": {
        "Días de mora": ("Resta la fecha de vencimiento de la fecha del corte anterior de la hoja 02 (Parámetros); sin "
                         "vencimiento, queda en blanco."),
        "Tramo": ("Clasifica la factura en su tramo de mora al corte anterior (corriente, 1 a 30, 31 a 60, 61 a 90, 91 a "
                  "180, 181 a 360 o más de 360 días). Sin días de mora queda en blanco."),
        "Clave": ("Une el segmento y el tramo al corte anterior (segmento|tramo) para agruparla en la hoja 03 (Tasas "
                  "históricas)."),
        "Sigue impago al corte": ("Busca la misma factura en el detalle actual (hoja 09) y toma su saldo, sin pasar del "
                                  "saldo que tenía al corte anterior ni bajar de cero: es lo que sigue sin cobrarse."),
        "Castigado": ("Suma lo castigado de la misma factura en la hoja 11 (Castigos del ejercicio), limitado al saldo "
                      "anterior que no sigue impago y nunca negativo."),
        "Pérdida observada": ("Suma lo que sigue impago al corte y lo castigado: es lo que no se recuperó de esa factura "
                              "en el año."),
    },
}

# Panel del dashboard (formato en graficos.py).
PANEL = {
    "poblacion": {"rotulo": "Cartera al corte", "total": "saldo"},
    "recalculado": {"rotulo": "Pérdida esperada recalculada", "total": "pce"},
    "registrado": {"rotulo": "Provisión registrada", "total": "provisionRegistrada"},
    "composicion": {"rotulo": "Pérdida esperada por tramo", "hoja": "05_Revelacion_NIIF7", "etiqueta": "Tramo de mora",
                    "valor": "Pérdida esperada"},
    "distribucion": {"rotulo": "Cartera por tramo", "hoja": "05_Revelacion_NIIF7", "etiqueta": "Tramo de mora",
                     "valor": "Importe en libros bruto"},
}


def _tramo_formula(celda: str) -> str:
    f = f'"{TRAMOS[-1]["n"]}"'
    for t in reversed(TRAMOS[:-1]):
        f = f'IF({celda}<={t["max"]},"{t["n"]}",{f})'
    return f'IF({celda}="","",{f})'


def _rango(hoja: str, col: str, n: int) -> str:
    return f"{hoja}${col}${FILA0}:${col}${FILA0 + max(n, 1) - 1}"


def _hoja(hojas, nombre):
    return next((h for h in hojas if h["name"] == nombre), None)


def _fila_concepto(hoja, columna, concepto):
    """Celda de «columna» en la fila cuya primera columna es «concepto»."""
    def ref(hojas, e):
        h = _hoja(hojas, hoja)
        if not h:
            return None
        j = [c[0] for c in h["cols"]].index(columna)
        for i, f in enumerate(h["rows"]):
            if problemas._texto(f[0]) == concepto:
                return problemas.celda(hojas, hoja, columna, i), f[j]
        return None
    return ref


def _fila_tramo(hojas, e):
    """Índice de la fila de la matriz cuyo «Segmento · Tramo:» abre la descripción."""
    h = _hoja(hojas, "04_Matriz_provisiones")
    msg = e.get("message") or ""
    for i, f in enumerate(h["rows"] if h else []):
        if msg.startswith(f"{problemas._texto(f[0])} · {problemas._texto(f[1])}:"):
            return h, i
    return h, None


def _tasa_cero(hojas, e):
    """Saldo al corte del tramo con tasa 0 % (04, fila del segmento y tramo)."""
    h, i = _fila_tramo(hojas, e)
    if i is None:
        return None
    return problemas.celda(hojas, "04_Matriz_provisiones", "Saldo al corte", i), h["rows"][i][8]


def _tasa_faltante(hojas, e):
    """Saldo del tramo que quedó sin tasa: facturas de esa clave sin «Tasa aplicada» en el Detalle (09)."""
    h, i = _fila_tramo(hojas, e)
    det = _hoja(hojas, "09_Detalle")
    if i is None or not det or not det["rows"]:
        return None
    clave = problemas._texto(h["rows"][i][2])
    n = len(det["rows"]) - 1
    rango = lambda col: (f"{problemas.celda(hojas, '09_Detalle', col, 0)}:"
                         f"{problemas.celda(hojas, '09_Detalle', col, n).split('!')[1]}")
    valor = sum(problemas._num(f[7]) or 0 for f in det["rows"]
                if problemas._texto(f[6]) == clave and problemas._num(f[9]) is None)
    formula = (f'SUMIFS({rango("Saldo")},{rango("Clave")},'
               f'{problemas.celda(hojas, "04_Matriz_provisiones", "Clave", i)},{rango("Tasa aplicada")},"")')
    return formula, valor


def _en_impago(hojas, e):
    """Saldo de las facturas marcadas «En impago» (más de 90 días) en el Detalle (09)."""
    det = _hoja(hojas, "09_Detalle")
    if not det or not det["rows"]:
        return None
    n = len(det["rows"]) - 1
    rango = lambda col: (f"{problemas.celda(hojas, '09_Detalle', col, 0)}:"
                         f"{problemas.celda(hojas, '09_Detalle', col, n).split('!')[1]}")
    valor = sum(problemas._num(f[7]) or 0 for f in det["rows"] if problemas._texto(f[11]) == "Sí")
    return f'SUMIF({rango("En impago")},"Sí",{rango("Saldo")})', valor


# De qué celda sale el importe de cada problema (ver procesadores/problemas.py).
REF_PROBLEMAS = {
    "TASA_FALTANTE": _tasa_faltante,                                   # saldo del tramo sin tasa (SUMIFS del 09)
    "TASA_CERO": _tasa_cero,                                           # saldo al corte del tramo con tasa 0 %
    "AJUSTE": _fila_concepto("01_Resumen", "Importe", "Ajuste propuesto"),      # pérdida esperada − provisión registrada
    "EN_IMPAGO": _en_impago,                                           # cartera con más de 90 días de mora
    "NO_DEDUCIBLE": _fila_concepto("07_Fiscal", "Importe", "Gasto no deducible"),  # exceso sobre los límites LRTI
}


def hojas(res: dict) -> list[dict]:
    d = res["detalle"]
    p = d["parametros"]
    f = d["fiscal"]
    t = {k: float(v) for k, v in res["totals"].items()}
    filas, ant, cas, mat = res["rows"], d["anterior"], d["castigos"], d["matriz"]
    nd, na, nc, nm = len(filas), len(ant), len(cas), len(mat)
    num = lambda k: None if p.get(k) in (None, "") else float(a_num(p.get(k)))

    manual = p.get("tasas") or {}
    parametros = [
        ["Corte del ejercicio", d["cortes"]["actual"], "Ficha del encargo"],
        ["Corte anterior (un año antes)", d["cortes"]["anterior"], "Base de la tasa histórica"],
        ["Tasa efectiva para descontar (%)", num("tasaDesc"), "5.5.17 b; 0 % en cartera de corto plazo sin componente financiero"],
        ["Plazo esperado de cobro (meses)", num("plazoBase"), "Juicio del auditor"],
        ["Escenario base: peso (%)", num("escBasePeso"), "5.5.17 a — importe ponderado por probabilidad"],
        ["Escenario base: ajuste a la historia (%)", num("escBaseAjuste"), "5.5.17 c, B5.5.52"],
        ["Escenario optimista: peso (%)", num("escOptPeso"), "5.5.17 a"],
        ["Escenario optimista: ajuste (%)", num("escOptAjuste"), "B5.5.52"],
        ["Escenario pesimista: peso (%)", num("escPesPeso"), "5.5.17 a"],
        ["Escenario pesimista: ajuste (%)", num("escPesAjuste"), "B5.5.52"],
        ["Factor prospectivo ponderado", _fx(f"(B{PAR['escBasePeso']}*(1+B{PAR['escBaseAjuste']}/100)+B{PAR['escOptPeso']}*(1+B{PAR['escOptAjuste']}/100)"
                                             f"+B{PAR['escPesPeso']}*(1+B{PAR['escPesAjuste']}/100))/(B{PAR['escBasePeso']}+B{PAR['escOptPeso']}+B{PAR['escPesPeso']})",
                                             d["factor"]), "Σ peso × (1 + ajuste) ÷ Σ peso"],
        ["Provisión registrada al cierre (mayor)", d["provisionRegistrada"], "Mayor contable"],
        ["Provisión al inicio del ejercicio", f["provIni"], "Mayor contable"],
        ["Límite anual deducible (%)", num("pctDeducible"), "LRTI Art. 10 num. 11"],
        ["Límite acumulado (%)", num("pctLimite"), "LRTI Art. 10 num. 11"],
        ["Tasa del impuesto (%)", num("tasaImp"), "Tarifa del contribuyente"],
        ["Provisión fiscal acumulada anterior", num("provFiscalAnt"), "En blanco: mínimo entre la provisión inicial y el límite acumulado"],
    ]
    fila_tasa = {}
    for k, v in manual.items():
        fila_tasa[k] = FILA0 + len(parametros)
        parametros.append([f"Tasa fijada por el auditor · {NOMBRE_TRAMO.get(k, k)} (%)", float(v), "Solo donde el tramo no tiene historia (B5.5.51)"])

    # 10 · Cartera anterior: días, tramo y pérdida observada con fórmulas.
    anterior = []
    for i, x in enumerate(ant):
        r = FILA0 + i
        anterior.append([x["factura"], x["cliente"], x["segmento"], x["vence"],
                         _fx(f'IF(D{r}="","",{P}$B${PAR["corteAnterior"]}-D{r})', x["dv"]),
                         _fx(_tramo_formula(f"E{r}"), NOMBRE_TRAMO.get(x["tramo"], "")),
                         _fx(f'C{r}&"|"&F{r}', f"{x['segmento']}|{NOMBRE_TRAMO.get(x['tramo'], '')}"), _n(x["saldo"]),
                         _fx(f"MAX(0,MIN(SUMIF({_rango(DET, 'A', nd)},A{r},{_rango(DET, 'H', nd)}),H{r}))", _n(x["sigue"])),
                         _fx(f"MAX(0,MIN(SUMIF({_rango(CAS, 'A', nc)},A{r},{_rango(CAS, 'C', nc)}),H{r}-I{r}))", _n(x["castigado"])),
                         _fx(f"I{r}+J{r}", _n(x["perdida"]))])

    # 03 · Tasas históricas por segmento y tramo.
    historicas = []
    for i, m in enumerate(mat):
        r = FILA0 + i
        historicas.append([m["segmento"], m["tramo"], m["clave"],
                           _fx(f"COUNTIF({_rango(ANT, 'G', na)},C{r})", m["docsHist"]),
                           _fx(f"SUMIF({_rango(ANT, 'G', na)},C{r},{_rango(ANT, 'H', na)})", _n(m["inicial"])),
                           _fx(f"SUMIF({_rango(ANT, 'G', na)},C{r},{_rango(ANT, 'K', na)})", _n(m["perdidaHist"])),
                           _fx(f'IF(E{r}=0,"",F{r}/E{r})', m["hist"])])

    # 04 · Matriz: histórica o fijada → × factor → tasa aplicada; saldo y pérdida desde el Detalle.
    matriz = []
    for i, m in enumerate(mat):
        r = FILA0 + i
        man = _fx(f"{P}$B${fila_tasa[m['k']]}/100", m["manual"] / 100) if m["k"] in fila_tasa else None
        matriz.append([m["segmento"], m["tramo"], m["clave"], _fx(f"{HIS}G{r}", m["hist"]), man,
                       _fx(f'IF(D{r}<>"",D{r},IF(E{r}<>"",E{r},""))', m["base"]), _fx(f"{P}$B${PAR['factor']}", d["factor"]),
                       _fx(f'IF(F{r}="","",MIN(F{r}*G{r},1))', m["ajustada"]),
                       _fx(f"SUMIF({_rango(DET, 'G', nd)},C{r},{_rango(DET, 'H', nd)})", _n(m["saldo"])),
                       _fx(f"SUMIF({_rango(DET, 'G', nd)},C{r},{_rango(DET, 'K', nd)})", _n(m["pce"]))])
    fin_mat = FILA0 + nm - 1

    # 09 · Detalle por factura.
    tasa_mat = f"INDEX({MAT}$H${FILA0}:$H${fin_mat},MATCH(G{{r}},{MAT}$C${FILA0}:$C${fin_mat},0))"
    desc = f"(1+{P}$B${PAR['tasaDesc']}/100)^({P}$B${PAR['plazoBase']}/12)"
    detalle = []
    for i, x in enumerate(filas):
        r = FILA0 + i
        tm = tasa_mat.format(r=r)
        detalle.append([x["id"], x["cliente"], x["segmento"], x["vence"],
                        _fx(f'IF(D{r}="","",{P}$B${PAR["corte"]}-D{r})', int(x["dias"]) if x["dias"] else None),
                        _fx(_tramo_formula(f"E{r}"), x["tramo"]), _fx(f'C{r}&"|"&F{r}', f"{x['segmento']}|{x['tramo']}"),
                        _n(x["saldo"]), float(x["tasaInd"]) if x["tasaInd"] else None,
                        _fx(f'IF(I{r}<>"",I{r}/100,IF(ISNA(MATCH(G{r},{MAT}$C${FILA0}:$C${fin_mat},0)),"",IF({tm}="","",{tm})))',
                            float(x["tasa"]) if x["tasa"] else None),
                        _fx(f'IF(J{r}="","",MAX(H{r}*J{r}/{desc},0))', _n(float(x["pce"])) if x["pce"] else None),
                        _fx(f'IF(E{r}="","",IF(E{r}>{IMPAGO_DIAS},"Sí","No"))', "Sí" if x["dias"] and int(x["dias"]) > IMPAGO_DIAS else ("No" if x["dias"] else ""))])
    fin_det = FILA0 + nd - 1
    s = lambda col, fin, v: _fx(f"SUM({col}{FILA0}:{col}{fin})", v)

    # 05 · Revelación por tramo (todos los segmentos).
    revel = []
    for i, tr in enumerate(TRAMOS):
        r = FILA0 + i
        saldo = sum(m["saldo"] for m in mat if m["k"] == tr["k"])
        perd = sum(m["pce"] for m in mat if m["k"] == tr["k"])
        revel.append([tr["n"], _fx(f"SUMIF({_rango(DET, 'F', nd)},A{r},{_rango(DET, 'H', nd)})", _n(saldo)),
                      _fx(f'IF(B{r}=0,"",D{r}/B{r})', perd / saldo if saldo else None),
                      _fx(f"SUMIF({_rango(DET, 'F', nd)},A{r},{_rango(DET, 'K', nd)})", _n(perd)),
                      "Sí" if tr["min"] > IMPAGO_DIAS else "No"])
    fin_rev = FILA0 + len(TRAMOS) - 1

    # 07 · Fiscal (orden FISC).
    pf = f"MIN({F_['provIni']},{F_['limite10']})" if f["pfEstimada"] else f"{P}B{PAR['provFiscalAnt']}"
    fiscal = [
        ["Cartera total al corte", _fx(f"SUM({_rango(DET, 'H', nd)})", _n(f["total"]))],
        ["Cartera corriente (créditos del ejercicio)", _fx(f'SUMIF({_rango(DET, "E", nd)},"<=0",{_rango(DET, "H", nd)})', _n(f["corriente"]))],
        ["Pérdida crediticia esperada al cierre", _fx(f"SUM({_rango(DET, 'K', nd)})", _n(f["pce"]))],
        ["Provisión al inicio del ejercicio", _fx(f"{P}B{PAR['provisionInicial']}", _n(f["provIni"]))],
        ["Castigos del ejercicio", _fx(f"SUM({_rango(CAS, 'C', nc)})" if nc else "0", _n(f["castigos"]))],
        ["Dotación neta del ejercicio", _fx(f"{F_['pce']}-{F_['provIni']}+{F_['castigos']}", _n(f["dotacion"]))],
        ["Límite anual (% sobre la cartera corriente)", _fx(f"{F_['corriente']}*{P}$B${PAR['pctDeducible']}/100", _n(f["limite1"]))],
        ["Límite acumulado (% sobre la cartera total)", _fx(f"{F_['total']}*{P}$B${PAR['pctLimite']}/100", _n(f["limite10"]))],
        ["Provisión fiscal acumulada anterior" + (" (estimada)" if f["pfEstimada"] else ""), _fx(pf, _n(f["provFiscalAnt"]))],
        ["Margen acumulado disponible", _fx(f"MAX({F_['limite10']}-{F_['provFiscalAnt']},0)", _n(f["margen"]))],
        ["Gasto deducible", _fx(f"MAX(MIN(MAX({F_['dotacion']},0),{F_['limite1']},{F_['margen']}),0)", _n(f["deducible"]))],
        ["Gasto no deducible", _fx(f"MAX(MAX({F_['dotacion']},0)-{F_['deducible']},0)", _n(f["noDeducible"]))],
        ["Provisión fiscal acumulada al cierre", _fx(f"{F_['provFiscalAnt']}+{F_['deducible']}", _n(f["provFiscalAcum"]))],
        ["Diferencia temporaria al cierre", _fx(f"MAX({F_['pce']}-{F_['provFiscalAcum']},0)", _n(f["dif"]))],
        ["Activo por impuesto diferido al cierre", _fx(f"{F_['dif']}*{P}$B${PAR['tasaImp']}/100", _n(f["dtaFin"]))],
        ["Activo por impuesto diferido inicial", _fx(f"MAX({F_['provIni']}-{F_['provFiscalAnt']},0)*{P}$B${PAR['tasaImp']}/100", _n(f["dtaIni"]))],
        ["Movimiento del diferido", _fx(f"{F_['dtaFin']}-{F_['dtaIni']}", _n(f["dtaMov"]))],
    ]
    movimiento = [
        ["Provisión al inicio del ejercicio", _fx(F_["provIni"], _n(f["provIni"]))],
        ["(−) Castigos del ejercicio (5.4.4)", _fx(F_["castigos"], _n(f["castigos"]))],
        ["(+) Dotación neta / (−) reversión del ejercicio", _fx(F_["dotacion"], _n(f["dotacion"]))],
        ["Provisión al cierre = pérdida crediticia esperada", _fx(f"B{FILA0}-B{FILA0 + 1}+B{FILA0 + 2}", _n(f["pce"]))],
    ]
    ref_asiento = {"dotacion": f"ABS({F_['dotacion']})", "castigos": F_["castigos"], "dtaMov": f"ABS({F_['dtaMov']})"}
    asientos = []
    for a in d["asientos"]:
        for i, l in enumerate(a["lineas"]):
            v = _fx(ref_asiento[a["ref"]], _n(l.get("d") if l.get("d") is not None else l.get("h")))
            asientos.append([f"{a['n']} · {a['titulo']}" if i == 0 else "", l["cta"], v if l.get("d") is not None else None,
                             v if l.get("h") is not None else None])
    fila_res = {k: FILA0 + i for i, k in enumerate(res["labels"])}
    ref_res = {"saldo": F_["total"], "pce": F_["pce"], "provisionRegistrada": f"{P}B{PAR['provisionRegistrada']}",
               "ajuste": f"B{fila_res['pce']}-B{fila_res['provisionRegistrada']}", "dotacion": F_["dotacion"],
               "castigos": F_["castigos"], "deducible": F_["deducible"], "noDeducible": F_["noDeducible"],
               "dtaFin": F_["dtaFin"], "dtaMov": F_["dtaMov"]}
    resumen = [[res["labels"][k], _fx(ref_res[k], _n(t[k]))] for k in res["labels"]]

    hoja = lambda name, label, cols, rows, total=None, explica=None: {"name": name, "label": label, "cols": cols, "rows": rows,
                                                                      "total": total, "explica": dict(explica or {})}
    fin_ant, fin_cas = FILA0 + na - 1, FILA0 + nc - 1
    return [
        hoja("01_Resumen", "Resumen", [["Concepto", "t"], ["Importe", "n"]], resumen, explica=EXPLICA["01_Resumen"]),
        hoja("02_Parametros", "Parámetros", [["Parámetro", "t"], ["Valor", "x"], ["Sustento", "t"]], parametros,
             explica=EXPLICA["02_Parametros"]),
        hoja("03_Tasas_historicas", "Tasas históricas",
             [["Segmento", "t"], ["Tramo", "t"], ["Clave", "t"], ["Facturas", "i"], ["Saldo al corte anterior", "n"],
              ["Impago o castigado un año después", "n"], ["Tasa histórica", "p"]], historicas,
             explica=EXPLICA["03_Tasas_historicas"]),
        hoja("04_Matriz_provisiones", "Matriz de provisiones",
             [["Segmento", "t"], ["Tramo", "t"], ["Clave", "t"], ["Tasa histórica", "p"], ["Tasa fijada", "p"], ["Tasa base", "p"],
              ["Factor prospectivo", "x"], ["Tasa aplicada", "p"], ["Saldo al corte", "n"], ["Pérdida esperada", "n"]], matriz,
             ["TOTAL", "", "", None, None, None, None, None, s("I", fin_mat, _n(t["saldo"])), s("J", fin_mat, _n(t["pce"]))],
             explica=EXPLICA["04_Matriz_provisiones"]),
        hoja("05_Revelacion_NIIF7", "Revelación NIIF 7 (35M/35N)",
             [["Tramo de mora", "t"], ["Importe en libros bruto", "n"], ["Tasa esperada promedio", "p"], ["Pérdida esperada", "n"],
              ["En impago (B5.5.37)", "t"]], revel, ["TOTAL", s("B", fin_rev, _n(t["saldo"])), None, s("D", fin_rev, _n(t["pce"])), ""],
             explica=EXPLICA["05_Revelacion_NIIF7"]),
        hoja("06_Movimiento", "Movimiento de la provisión (NIIF 7 35H)", [["Concepto", "t"], ["Importe", "n"]], movimiento,
             explica=EXPLICA["06_Movimiento"]),
        hoja("07_Fiscal", "Fiscal e impuesto diferido", [["Concepto", "t"], ["Importe", "n"]], fiscal, explica=EXPLICA["07_Fiscal"]),
        hoja("08_Asientos", "Asientos propuestos", [["Asiento", "t"], ["Cuenta", "t"], ["Debe", "n"], ["Haber", "n"]], asientos,
             explica=EXPLICA["08_Asientos"]),
        hoja("09_Detalle", "Detalle por factura",
             [["Factura", "t"], ["Cliente", "t"], ["Segmento", "t"], ["Vencimiento", "d"], ["Días de mora", "i"], ["Tramo", "t"],
              ["Clave", "t"], ["Saldo", "n"], ["Tasa individual (%)", "x"], ["Tasa aplicada", "p"], ["Pérdida esperada", "n"], ["En impago", "t"]],
             detalle, ["TOTAL", "", "", "", None, "", "", s("H", fin_det, _n(t["saldo"])), None, None, s("K", fin_det, _n(t["pce"])), ""],
             explica=EXPLICA["09_Detalle"]),
        hoja("10_Cartera_anterior", "Cartera del corte anterior",
             [["Factura", "t"], ["Cliente", "t"], ["Segmento", "t"], ["Vencimiento", "d"], ["Días de mora", "i"], ["Tramo", "t"], ["Clave", "t"],
              ["Saldo", "n"], ["Sigue impago al corte", "n"], ["Castigado", "n"], ["Pérdida observada", "n"]], anterior,
             ["TOTAL", "", "", "", None, "", "", s("H", fin_ant, _n(sum(x["saldo"] for x in ant))), s("I", fin_ant, _n(sum(x["sigue"] for x in ant))),
              s("J", fin_ant, _n(sum(x["castigado"] for x in ant))), s("K", fin_ant, _n(sum(x["perdida"] for x in ant)))] if na else None,
             explica=EXPLICA["10_Cartera_anterior"]),
        hoja("11_Castigos", "Castigos del ejercicio", [["Factura", "t"], ["Cliente", "t"], ["Importe castigado", "n"]],
             [[c["id"], c["cliente"], _n(c["importe"])] for c in cas],
             ["TOTAL", "", s("C", fin_cas, _n(f["castigos"]))] if nc else None),
        hoja("12_Problemas", "Problemas encontrados", [["Código", "t"], ["Descripción", "t"], ["Importe", "n"]],
             [[e["code"], e["message"], _n(e["amount"])] for e in res["exceptions"]]),
    ]


# --- definición (ficha CXC-PCE-01) ---------------------------------------------

def _req(id, doc, ds, proc, purpose, required=True, formats=("xlsx", "csv"), use="calculo", content=""):
    r = {"id": id, "document": doc, "formats": list(formats), "purpose": purpose, "procedure": proc, "required": required, "use": use}
    if ds:
        r["dataset"] = ds
    if content:
        r["content"] = content
    return r


def definicion() -> dict:
    cartera = "Una fila por factura: N° de factura, cliente, vencimiento y saldo (segmento y tasa individual opcionales); sin filas de total."
    return {
        "name": "Pérdida crediticia esperada · enfoque simplificado (NIIF 9)",
        "area": "Cuentas por cobrar",
        "processor": "pce_simplificada_niif9",
        "frameworks": ["NIIF completas"],
        "summary": ("Recalcula la corrección de valor de las cuentas por cobrar comerciales con el enfoque simplificado de la NIIF 9 "
                    "(pérdida esperada durante toda la vida, 5.5.15) y una matriz de provisiones (B5.5.35): tasas históricas por tramo "
                    "medidas con la cartera del corte anterior y los castigos, ajustadas con escenarios prospectivos (5.5.17, B5.5.52)."),
        "source": {"organization": "IFRS Foundation", "type": "Norma contable", "date": "",
                   "document": "NIIF 9 Instrumentos financieros · párr. 5.5.15, 5.5.17, 5.4.4, B5.5.35, B5.5.37, B5.5.51–B5.5.53; NIIF 7 35H, 35M, 35N",
                   "url": "https://www.ifrs.org/issued-standards/list-of-standards/ifrs-9-financial-instruments/"},
        "nia": [
            {"document": "NIA 540 (Revisada)", "section": "párr. 13 y 17–30",
             "requirement": "Estimación contable: evaluar el método (matriz), los datos (cartera y castigos) y los supuestos (escenarios, tasas fijadas) y el posible sesgo."},
            {"document": "NIA 500", "section": "párr. 9", "requirement": "Evaluar exactitud e integridad de los anexos de cartera contra el mayor."},
            {"document": "NIA 505", "section": "párr. 7", "requirement": "Considerar confirmaciones de saldos significativos."},
            {"document": "NIA 560", "section": "párr. 6", "requirement": "Cobros posteriores al cierre como evidencia sobre la estimación."},
        ],
        "calculo": [
            "Tramo de mora de cada factura al corte: corriente, 1–30, 31–60, 61–90, 91–180, 181–360 y más de 360 días (segmento opcional, B5.5.35).",
            "Tasa histórica por segmento y tramo = (lo que un año después sigue impago + lo castigado) ÷ saldo al corte anterior (B5.5.35, B5.5.37, 5.4.4).",
            "Sin historia en un tramo, el auditor fija la tasa con su sustento: ningún tramo queda en cero por omisión.",
            "Factor prospectivo = Σ peso × (1 + ajuste) ÷ Σ peso de los escenarios base, optimista y pesimista (5.5.17 a y c, B5.5.52).",
            "Pérdida esperada por factura = saldo × tasa aplicada ÷ (1 + tasa efectiva)^(plazo/12) (5.5.17 b); tasa individual si hay evidencia específica.",
            "Ajuste propuesto = pérdida esperada − provisión registrada; movimiento de la provisión (NIIF 7 35H) y matriz para las notas (35M/35N).",
            "Tributario: límite anual 1 % de la cartera corriente, acumulado 10 % de la cartera total e impuesto diferido.",
        ],
        "fields": _CARTERA, "rules": [], "control": "saldo", "primary": "ajuste",
        "campos": CAMPOS, "tipos": TIPOS, "parametros": {k: v for k, v in PARAMETROS.items() if k != "tasas"},
        "etiquetas_parametros": ETIQUETAS_PARAM, "tramos": [{"k": t["k"], "tramo": t["n"]} for t in TRAMOS],
        "cedulas": [[n, l] for n, l in CEDULAS],
        "program": [
            {"code": "CXCPCE-01", "objective": "Integridad de la cartera", "risk": "Anexo incompleto o no conciliado", "assertion": "Integridad",
             "procedure": "Conciliar la cartera por factura con el mayor al corte", "evidence": "Cartera por factura y mayor",
             "criterion": "Diferencia dentro de tolerancia o explicada", "source": "NIA 500 párr. 9"},
            {"code": "CXCPCE-02", "objective": "Tasas históricas", "risk": "Tasas sin sustento en la experiencia de pérdidas", "assertion": "Valoración",
             "procedure": "Medir por tramo la pérdida observada un año después (impago o castigo) sobre la cartera del corte anterior",
             "evidence": "Cartera del corte anterior y castigos del año", "criterion": "Tasa por tramo medida o fijada con sustento",
             "source": "NIIF 9 B5.5.35, B5.5.37 · NIA 540"},
            {"code": "CXCPCE-03", "objective": "Información prospectiva", "risk": "Historia sin ajustar a condiciones actuales y futuras", "assertion": "Valoración",
             "procedure": "Evaluar los escenarios, sus pesos y ajustes, y su sustento", "evidence": "Proyecciones, indicadores del sector y de la economía",
             "criterion": "Factor prospectivo documentado", "source": "NIIF 9 5.5.17, B5.5.52"},
            {"code": "CXCPCE-04", "objective": "Medición de la pérdida esperada", "risk": "Corrección de valor mal calculada", "assertion": "Valoración",
             "procedure": "Recalcular la pérdida esperada por factura con la matriz y compararla con la provisión registrada",
             "evidence": "Detalle por factura", "criterion": "Ajuste cuantificado", "source": "NIIF 9 5.5.15, B5.5.35"},
            {"code": "CXCPCE-05", "objective": "Movimiento, castigos y revelación", "risk": "Castigos sin sustento o revelación incompleta", "assertion": "Presentación",
             "procedure": "Conciliar el movimiento de la provisión y preparar la matriz de revelación", "evidence": "Castigos, mayor, notas",
             "criterion": "Movimiento conciliado; nota NIIF 7 completa", "source": "NIIF 9 5.4.4 · NIIF 7 35H, 35M, 35N"},
            {"code": "CXCPCE-06", "objective": "Tratamiento fiscal", "risk": "Deducción excesiva o diferido mal medido", "assertion": "Presentación",
             "procedure": "Aplicar los límites de deducibilidad y medir el impuesto diferido", "evidence": "Parámetros fiscales",
             "criterion": "Deducible y diferido recalculados", "source": "LRTI Art. 10 num. 11 · NIC 12"},
            {"code": "CXCPCE-07", "objective": "Cobros posteriores", "risk": "Estimación no contrastada con hechos posteriores", "assertion": "Valoración",
             "procedure": "Cotejar cobros posteriores al cierre con la cartera en impago y con tasa alta", "evidence": "Estados de cuenta, depósitos posteriores",
             "criterion": "Diferencias evaluadas", "source": "NIA 560 párr. 6"},
        ],
        "requests": [
            _req("RQ-001", "Cartera por factura al corte del ejercicio", "actual", "CXCPCE-01", "Población a medir y conciliar con el mayor", content=cartera),
            _req("RQ-002", "Cartera por factura al corte del ejercicio anterior", "anterior", "CXCPCE-02", "Medir la tasa histórica de pérdida por tramo", content=cartera),
            _req("RQ-003", "Castigos del ejercicio por factura", "castigos", "CXCPCE-05", "Pérdidas dadas de baja en el año (5.4.4)", required=False,
                 content="Una fila por factura castigada: N° de factura, cliente e importe castigado."),
            _req("RQ-004", "Información prospectiva usada para el ajuste (proyecciones, indicadores del sector)", None, "CXCPCE-03",
                 "Sustento de los escenarios", formats=("pdf", "docx", "xlsx"), use="soporte"),
            _req("RQ-005", "Política de crédito y cobranza y gestión de clientes en mora", None, "CXCPCE-04",
                 "Sustento de tasas fijadas y tasas individuales", formats=("pdf", "docx"), use="soporte"),
            _req("RQ-006", "Cobros posteriores al cierre", None, "CXCPCE-07", "Evidencia sobre la estimación",
                 formats=("xlsx", "pdf"), use="soporte", required=False),
        ],
    }


def validar_definicion(d: dict) -> dict:
    ds = [r.get("dataset") for r in d.get("requests") or [] if r.get("dataset")]
    if "actual" not in ds or len(ds) != len(set(ds)) or any(x not in DATASETS for x in ds):
        raise ValueError("La definición necesita un requerimiento por anexo y el de la cartera al corte (actual).")
    if not str(d.get("name") or "").strip() or not str(d.get("area") or "").strip():
        raise ValueError("Indique nombre y rubro de la herramienta.")
    return d


def _ej(id, cliente, vence, saldo, **extra):
    return {"id": id, "cliente": cliente, "vence": vence, "saldo": saldo, "_row": 2, **extra}


# Ejemplo numérico de control (ficha E.6): al corte anterior el tramo 31–60 tenía
# 1.000 (F-10) y 1.000 (F-11); un año después F-10 sigue con 150 impago y F-11 se
# castigó por 50 → tasa histórica 200 ÷ 2.000 = 10 %. Con escenarios 60 % × 0 %,
# 20 % × −10 % y 20 % × +25 %, factor 1,03 → tasa 10,3 %. Una factura de 3.000 en
# ese tramo espera perder 309,00.
EJEMPLO = {
    "corte": "2025-12-31",
    "parametros": {"escBasePeso": 60, "escBaseAjuste": 0, "escOptPeso": 20, "escOptAjuste": -10, "escPesPeso": 20, "escPesAjuste": 25},
    "datasets": {
        "anterior": [_ej("F-10", "A", "2024-11-15", "1000"), _ej("F-11", "B", "2024-11-20", "1000")],
        "actual": [_ej("F-10", "A", "2024-11-15", "150"), _ej("F-20", "C", "2025-11-15", "3000")],
        "castigos": [{"id": "F-11", "cliente": "B", "importe": "50", "_row": 2}],
    },
}
