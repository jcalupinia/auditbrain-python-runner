"""Préstamos y obligaciones financieras: NIIF 9 / NIC 1 en NIIF completas y Secciones 11 y 4 en la NIIF para las PYMES.

Versión simple que cumple la norma, préstamo por préstamo (un solo anexo del cliente + parámetros de la entidad):

1. Condiciones y tabla contractual: cuota del sistema francés (PAGO), alemán (capital constante) o bullet
   (interés periódico y capital al vencimiento); tasa periódica = tasa nominal anual × meses ÷ 12.
2. Medición inicial al valor razonable neto de los costos de transacción (NIIF 9 5.1.1 / PYMES 11.13):
   importe neto recibido = monto − comisiones y costos de transacción.
3. Tasa de interés efectiva (TIE, Apéndice A): la tasa que iguala los pagos contractuales con el importe neto
   recibido (TIR de Excel sobre los flujos de la tabla; bisección en Python). Las comisiones integran la TIE.
4. Costo amortizado (NIIF 9 4.2.1, 5.3.1 y Apéndice A / 11.15–11.20): interés_t = saldo inicial_t × TIE; capital_t = pago_t −
   interés_t; saldo final_t = saldo inicial_t − capital_t. Al corte se suma el interés devengado desde el
   último vencimiento (lineal por días dentro del período).
5. Recálculo del interés nominal y del gasto financiero del ejercicio; interés devengado no registrado;
   comisiones llevadas a gasto (costo pendiente de amortizar).
6. Confirmación bancaria: saldo confirmado vs registrado y vs tabla; pagos del año recalculados vs informados.
7. Covenants y clasificación (NIC 1 69–76, modificaciones 2020/2022 vigentes desde 2024 / PYMES 4.7):
   corriente = lo que vence en 12 meses; si un covenant que debía cumplirse al cierre o antes (NIC 1 72B,
   columna «Fecha de medición del covenant») se incumplió al corte y no hubo dispensa obtenida hasta el corte
   con gracia de al menos 12 meses, toda la deuda es corriente (74–75). Un covenant que se mide después del
   corte no reclasifica, pero exige la revelación del párrafo 76ZA. Los impagos de principal o intereses y las
   infracciones de otras cláusulas no subsanadas al cierre se revelan (NIIF 7 18–19 / PYMES 11.47).
8. Endeudamiento (analítica de auditoría, no requisito NIIF): deuda/activos, deuda/patrimonio, deuda/EBITDA,
   cobertura de intereses y DSCR contra los límites de los contratos. **El DSCR se calcula con la definición del
   contrato cuando el cliente la informa (parámetros «Definición contractual del DSCR» y «Servicio de la deuda del
   DSCR según el contrato»). Si no hay definición contractual, la herramienta muestra su propia métrica, etiquetada
   «DSCR analítico de la firma», que NO concluye incumplimiento del covenant ni reclasifica deuda: es solo un
   indicador para el auditor.**
9. Modificación de condiciones (adenda): prueba del 10 % de la NIIF 9 3.3.2 y B3.3.6 sobre el anexo opcional de
   flujos («Original» / «Modificado»), descontados a la tasa de interés efectiva original. **Sin los flujos
   contractuales originales restantes y los modificados, más la fecha de la modificación, la prueba no concluye:
   el resultado queda vacío y se emite «dato insuficiente: conclusión bloqueada».** En la NIIF para las PYMES la
   Sección 11 (11.37) exige condiciones «sustancialmente diferentes» sin umbral cuantitativo: esa prueba del 10 %
   no existe en PYMES y el módulo la aplica por analogía (jerarquía 10.6), como juicio del auditor. El módulo NO
   remide el pasivo después de la modificación: las cédulas 04 a 13 siguen el contrato original.

Cada importe del libro Excel es una fórmula viva que remite a 02_Parametros, 03_Prestamos y 05_Tabla_amortizacion.
"""
from __future__ import annotations

import calendar
from datetime import date

from openpyxl.utils import get_column_letter

from backend.app.aud.niif.procesadores.base import (  # noqa: F401  (a_num y filas_mapeadas los usa el ciclo)
    FILA0, a_fecha, a_num, campo, edicion_pymes, es_pymes, filas_mapeadas, fx, hoja, m as _m, norm, problema, r2,
    ref, req, suma, validar_campos, validar_definicion_generica,
)

VERSION = "prestamos_obligaciones 1.0"
RUBRO = "PRESTAMOS"

_PRESTAMOS = [
    campo("id", "Operación", alias=("operacion", "numero de operacion", "prestamo", "credito", "codigo"), ejemplo="OP-1001"),
    campo("banco", "Banco / acreedor", alias=("banco", "acreedor", "institucion", "entidad financiera"), ejemplo="Banco del Pacífico"),
    campo("desembolso", "Fecha de desembolso", "date", alias=("fecha desembolso", "desembolso", "fecha de concesion", "fecha inicio"), ejemplo="2025-01-15"),
    campo("monto", "Monto desembolsado", "number", alias=("monto", "capital original", "monto original", "valor del prestamo"), ejemplo=100000),
    campo("plazo", "Plazo (meses)", "number", alias=("plazo", "plazo meses", "meses"), ejemplo=36),
    campo("tasa", "Tasa nominal anual (%)", "number", alias=("tasa", "tasa nominal", "tasa anual", "tasa de interes"), ejemplo=10.5),
    campo("periodicidad", "Periodicidad de pago (mensual/trimestral/semestral/anual)", alias=("periodicidad", "frecuencia", "forma de pago"), ejemplo="Mensual"),
    campo("sistema", "Sistema de amortización (francés/alemán/bullet)", alias=("sistema", "sistema de amortizacion", "tipo de cuota"), ejemplo="Francés"),
    campo("comisiones", "Comisiones y costos de transacción", "number", False, ("comisiones", "costos de transaccion", "gastos de apertura")),
    campo("trat_comisiones", "Tratamiento de las comisiones por el cliente (TIE/gasto)", "text", False, ("tratamiento comisiones", "comisiones a gasto")),
    campo("pagos_anio", "Pagos realizados en el año (capital + interés)", "number", False, ("pagos del año", "pagos realizados", "servicio de deuda")),
    campo("confirmado", "Saldo de capital confirmado por el banco", "number", False, ("saldo confirmado", "confirmacion bancaria", "confirmado")),
    campo("saldo_reg", "Saldo de capital registrado", "number", alias=("saldo registrado", "saldo capital", "saldo contable", "saldo"), ejemplo=0),
    campo("int_reg", "Intereses por pagar registrados", "number", False, ("intereses por pagar", "interes devengado registrado")),
    campo("gasto_reg", "Gasto financiero registrado del año", "number", False, ("gasto financiero", "gasto de intereses", "interes registrado")),
    campo("cp_reg", "Porción corriente registrada", "number", False, ("porcion corriente", "corriente registrado", "corto plazo")),
    campo("covenant", "Covenant (deuda/activos, deuda/patrimonio, deuda/EBITDA, cobertura de intereses, DSCR)", "text", False,
          ("covenant", "condicion financiera", "ratio pactado")),
    campo("incumplido", "Incumplimiento de covenant declarado (sí/no)", "text", False, ("incumplimiento", "incumplido", "covenant incumplido")),
    campo("fecha_dispensa", "Fecha de la dispensa del banco", "date", False, ("fecha dispensa", "waiver", "fecha waiver")),
    campo("gracia_hasta", "Fin del período de gracia de la dispensa", "date", False, ("gracia hasta", "fin de la gracia", "moratoria hasta")),
    campo("fecha_covenant", "Fecha de medición del covenant", "date", False,
          ("fecha covenant", "fecha de medicion", "fecha de medicion del covenant", "medicion covenant", "fecha de prueba del covenant")),
    campo("modificado", "Modificación de condiciones en el ejercicio (sí/no)", "text", False,
          ("modificado", "modificacion", "adenda", "refinanciacion", "reestructuracion", "modificacion de condiciones")),
    campo("fecha_modificacion", "Fecha de la modificación (adenda)", "date", False,
          ("fecha modificacion", "fecha de la adenda", "fecha adenda", "fecha de refinanciacion")),
    campo("comision_modificacion", "Comisiones pagadas al prestamista netas de las recibidas por la modificación", "number", False,
          ("comisiones modificacion", "comisiones adenda", "comision de reestructuracion", "comisiones netas de la modificacion")),
]

# Anexo opcional: flujos contractuales para la prueba del 10 % (NIIF 9 3.3.2 y B3.3.6). Una fila por flujo.
_FLUJOS = [
    campo("id", "Operación", alias=("operacion", "numero de operacion", "prestamo", "credito", "codigo"), ejemplo="OP-103"),
    campo("escenario", "Escenario (original / modificado)", alias=("escenario", "condiciones", "version", "tipo de flujo", "tipo"), ejemplo="Original"),
    campo("fecha", "Fecha del flujo", "date", alias=("fecha", "fecha de pago", "vencimiento", "fecha del flujo"), ejemplo="2026-01-01"),
    campo("importe", "Importe del flujo (pago del prestatario)", "number", alias=("importe", "flujo", "pago", "valor", "cuota"), ejemplo=45948.59),
]
CAMPOS = {"prestamos": _PRESTAMOS, "flujos": _FLUJOS}
TIPOS = {"prestamos": "prestamos", "flujos": "flujos"}
DATASETS = tuple(TIPOS)
PRINCIPAL = "prestamos"
CONTROL = "saldo_reg"
TOTAL_EJEMPLO = "pasivo"

PARAMETROS = {"totalActivos": None, "patrimonio": None, "ebitda": None, "ebit": None, "efectivoServicioDeuda": None,
              "baseCobertura": "EBITDA", "limDeudaActivos": None, "limDeudaPatrimonio": None, "limDeudaEbitda": None,
              "limCobertura": None, "limDSCR": None, "defDSCR": "", "servicioDSCRContrato": None}
PARAM_NEGATIVOS = ("patrimonio", "ebitda", "ebit", "efectivoServicioDeuda")
ETIQUETAS_PARAM = {
    "totalActivos": "Total de activos de la entidad al corte",
    "patrimonio": "Patrimonio de la entidad al corte",
    "ebitda": "EBITDA del ejercicio",
    "ebit": "EBIT (utilidad operativa) del ejercicio",
    "efectivoServicioDeuda": "Efectivo disponible para el servicio de la deuda",
    "baseCobertura": "Base de la cobertura de intereses (EBITDA / EBIT)",
    "limDeudaActivos": "Límite máximo deuda / activos (veces)",
    "limDeudaPatrimonio": "Límite máximo deuda / patrimonio (veces)",
    "limDeudaEbitda": "Límite máximo deuda / EBITDA (veces)",
    "limCobertura": "Límite mínimo de cobertura de intereses (veces)",
    "limDSCR": "Límite mínimo DSCR (veces)",
    "defDSCR": "Definición contractual del DSCR (numerador ÷ denominador, según el contrato)",
    "servicioDSCRContrato": "Servicio de la deuda del DSCR según el contrato",
}
_TXT_PARAM = ("baseCobertura", "defDSCR")
_NUM_PARAM = [k for k in PARAMETROS if k not in _TXT_PARAM]
DSCR_ANALITICO = "DSCR analítico de la firma"

COL = {c["key"]: get_column_letter(i + 1) for i, c in enumerate(_PRESTAMOS)}
MESES = {"Mensual": 1, "Trimestral": 3, "Semestral": 6, "Anual": 12}
RATIOS = ["Deuda / activos", "Deuda / patrimonio", "Deuda / EBITDA", "Cobertura de intereses", "DSCR"]


def kind(dataset: str) -> str:
    return TIPOS[dataset]


# --- normalización de textos (lo que se escribe en 03_Prestamos) ---------------------

def _si(v) -> str:
    s = norm(v)
    if not s:
        return ""
    if s in ("si", "s", "yes", "y", "x", "1", "true", "verdadero"):
        return "Sí"
    if s in ("no", "n", "0", "false", "falso"):
        return "No"
    return "?"


def _periodicidad(v) -> str:
    s = norm(v)
    for k, (pref, num) in (("Mensual", ("mens", "1")), ("Trimestral", ("trim", "3")), ("Semestral", ("sem", "6")), ("Anual", ("anu", "12"))):
        if s.startswith(pref) or s == num:
            return k
    return ""


def _sistema(v) -> str:
    s = norm(v)
    if s.startswith("franc") or "cuotafija" in s or "cuotaconstante" in s:
        return "Francés"
    if s.startswith("alem") or "capitalconstante" in s or "capitalfijo" in s:
        return "Alemán"
    if s.startswith(("bullet", "americ")) or "vencimiento" in s:
        return "Bullet"
    return ""


def _trat(v) -> str:
    s = norm(v)
    if not s:
        return ""
    if s.startswith(("tie", "efect", "amort", "difer", "costoamort")):
        return "TIE"
    if s.startswith(("gast", "result")):
        return "Gasto"
    return "?"


def _covenant(v) -> str:
    s = norm(v)
    if not s:
        return ""
    if "cobertura" in s or s.startswith("interes"):
        return "Cobertura de intereses"
    if "dscr" in s or "servicio" in s:
        return "DSCR"
    if "patrimonio" in s:
        return "Deuda / patrimonio"
    if "activo" in s:
        return "Deuda / activos"
    if "ebitda" in s:
        return "Deuda / EBITDA"
    return "?"


def _escenario(v) -> str:
    s = norm(v)
    if not s:
        return ""
    if s.startswith(("orig", "contract", "anter", "previ")):
        return "Original"
    if s.startswith(("modif", "nuev", "adend", "reestruct", "refinan")):
        return "Modificado"
    return "?"


def validar_filas(tipo: str, filas: list) -> dict:
    if tipo == "flujos":
        r = validar_campos(_FLUJOS, filas, unico=None)     # el mismo préstamo tiene muchos flujos
        for f in filas:
            if str(f.get("escenario", "") or "").strip() and _escenario(f.get("escenario")) == "?":
                r["errors"].append({"row": f.get("_row"), "field": "escenario", "message": "Escenario: use «original» o «modificado»."})
        r["ok"] = not r["errors"]
        return r
    r = validar_campos(CAMPOS[tipo], filas)
    lbl = {c["key"]: c["label"] for c in _PRESTAMOS}
    for f in filas:
        fila = f.get("_row")
        err = lambda k, msg: r["errors"].append({"row": fila, "field": k, "message": f"{lbl[k]}: {msg}"})
        if str(f.get("periodicidad", "") or "").strip() and not _periodicidad(f.get("periodicidad")):
            err("periodicidad", "use mensual, trimestral, semestral o anual.")
        if str(f.get("sistema", "") or "").strip() and not _sistema(f.get("sistema")):
            err("sistema", "use francés, alemán o bullet.")
        if _trat(f.get("trat_comisiones")) == "?":
            err("trat_comisiones", "responda TIE o gasto.")
        if _covenant(f.get("covenant")) == "?":
            err("covenant", "use deuda/activos, deuda/patrimonio, deuda/EBITDA, cobertura de intereses o DSCR.")
        if _si(f.get("incumplido")) == "?":
            err("incumplido", "responda sí o no.")
        if _si(f.get("modificado")) == "?":
            err("modificado", "responda sí o no.")
        monto, plazo, tasa, com = (a_num(f.get(k)) for k in ("monto", "plazo", "tasa", "comisiones"))
        if monto is not None and monto <= 0:
            err("monto", "debe ser mayor que cero.")
        if plazo is not None and plazo <= 0:
            err("plazo", "debe ser mayor que cero.")
        if tasa is not None and not 0 <= tasa <= 100:
            err("tasa", "use un porcentaje entre 0 y 100.")
        if com is not None and (com < 0 or (monto and com >= monto)):
            err("comisiones", "no pueden ser negativas ni iguales o mayores que el monto.")
    r["ok"] = not r["errors"]
    return r


# --- aritmética idéntica a Excel -------------------------------------------------------

def _meses(a: date, b: date) -> int:
    """DATEDIF(a;b;"m"): meses completos."""
    return (b.year - a.year) * 12 + b.month - a.month - (1 if b.day < a.day else 0)


def _edate(d: date, n: int) -> date:
    y, mm = divmod(d.month - 1 + n, 12)
    y, mm = d.year + y, mm + 1
    return date(y, mm, min(d.day, calendar.monthrange(y, mm)[1]))


def _frac(d0: date, k: int, m: int, n: int, en: date) -> float:
    """Fracción del período k+1 transcurrida a la fecha `en` (días reales entre vencimientos)."""
    if k >= n:
        return 0
    a, b = _edate(d0, k * m), _edate(d0, (k + 1) * m)
    return (en - a).days / (b - a).days


def _tir(flujos: list) -> float:
    """TIR de Excel por bisección: tasa que anula el VAN de los flujos (flujo 0 negativo, luego pagos)."""
    van = lambda r: sum(f / (1 + r) ** t for t, f in enumerate(flujos))
    lo, hi = -0.99, 10.0
    if not (van(lo) >= 0 >= van(hi)):
        raise ValueError("No existe una tasa de interés efectiva para los flujos del préstamo.")
    for _ in range(300):
        mid = (lo + hi) / 2
        if van(mid) > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


# --- cálculo ---------------------------------------------------------------------------

def _tabla(c: dict) -> list:
    """Tabla contractual y de costo amortizado; el período 0 es el desembolso."""
    i, n, monto = c["i"], int(c["n"]), c["monto"]
    filas = [{"id": c["id"], "t": 0, "vence": c["desembolso"].isoformat(), "pago": None, "ini": None, "int_nom": None, "cap": None,
              "fin": monto, "flujo": -c["neto"], "ca_ini": None, "int_tie": None, "amort": None, "ca_fin": c["neto"]}]
    for t in range(1, n + 1):
        ini = filas[-1]["fin"]
        inte = ini * i
        if c["sistema"] == "Francés":
            pago = c["cuota"]
        elif c["sistema"] == "Alemán":
            pago = monto / c["n"] + inte
        else:
            pago = inte if t < n else inte + ini
        cap = pago - inte
        filas.append({"id": c["id"], "t": t, "vence": _edate(c["desembolso"], t * c["m"]).isoformat(), "pago": pago, "ini": ini,
                      "int_nom": inte, "cap": cap, "fin": ini - cap, "flujo": pago})
    c["tie"] = _tir([x["flujo"] for x in filas])
    for x, ant in zip(filas[1:], filas):
        x["ca_ini"] = ant["ca_fin"]
        x["int_tie"] = x["ca_ini"] * c["tie"]
        x["amort"] = x["pago"] - x["int_tie"]
        x["ca_fin"] = x["ca_ini"] - x["amort"]
    return filas


def _prestamo(f: dict, corte: date, inicio: date, probs: list):
    g = lambda k: a_num(f.get(k))
    pid = str(f.get("id", "") or "").strip()
    d0 = a_fecha(f.get("desembolso"))
    if not pid or d0 is None or g("monto") is None or g("plazo") is None or g("tasa") is None or g("saldo_reg") is None:
        raise ValueError(f"Préstamo {pid or '(sin código)'}: faltan fecha de desembolso, monto, plazo, tasa o saldo registrado.")
    per, sis = _periodicidad(f.get("periodicidad")), _sistema(f.get("sistema"))
    if not per or not sis:
        raise ValueError(f"Préstamo {pid}: periodicidad o sistema de amortización no reconocidos.")
    if g("monto") <= 0 or g("plazo") <= 0 or not 0 <= g("tasa") <= 100:
        raise ValueError(f"Préstamo {pid}: monto y plazo deben ser positivos y la tasa entre 0 % y 100 %.")
    if d0 > corte:
        probs.append(problema("NO_DESEMBOLSADO", f"{pid}: desembolso del {d0.isoformat()}, posterior al corte; no es un pasivo al corte (NIIF 9 3.1.1). Revele si es un hecho posterior significativo."))
        return None
    m = MESES[per]
    c = {"id": pid, "banco": str(f.get("banco", "") or "").strip(), "desembolso": d0, "monto": g("monto"), "plazo": g("plazo"),
         "tasa": g("tasa"), "periodicidad": per, "sistema": sis, "comisiones": g("comisiones"),
         "trat_comisiones": _trat(f.get("trat_comisiones")), "pagos_anio": g("pagos_anio"), "confirmado": g("confirmado"),
         "saldo_reg": g("saldo_reg"), "int_reg": g("int_reg"), "gasto_reg": g("gasto_reg"), "cp_reg": g("cp_reg"),
         "covenant": _covenant(f.get("covenant")), "incumplido": _si(f.get("incumplido")),
         "fecha_dispensa": a_fecha(f.get("fecha_dispensa")), "gracia_hasta": a_fecha(f.get("gracia_hasta")),
         "fecha_covenant": a_fecha(f.get("fecha_covenant")), "modificado": _si(f.get("modificado")) or "No",
         "fecha_modificacion": a_fecha(f.get("fecha_modificacion")), "comision_modificacion": g("comision_modificacion"),
         "_row": f.get("_row"), "m": m}
    c["n"] = c["plazo"] / m
    if c["n"] != int(c["n"]):
        raise ValueError(f"Préstamo {pid}: el plazo de {c['plazo']:g} meses no es múltiplo de la periodicidad ({per}).")
    com = c["comisiones"] or 0
    if com < 0 or com >= c["monto"]:
        raise ValueError(f"Préstamo {pid}: las comisiones no pueden ser negativas ni iguales o mayores que el monto.")
    c["com"] = com
    c["neto"] = c["monto"] - com
    c["i"] = c["tasa"] / 100 * m / 12
    n = c["n"]
    c["cuota"] = (c["monto"] / n if c["i"] == 0 else c["monto"] * c["i"] * (1 + c["i"]) ** n / ((1 + c["i"]) ** n - 1)) if sis == "Francés" else None
    c["tabla"] = _tabla(c)
    c["tie_anual"] = (1 + c["tie"]) ** (12 / m) - 1
    c["ef_contractual"] = (1 + c["i"]) ** (12 / m) - 1
    c["dif_tasa"] = c["tie_anual"] - c["ef_contractual"]
    T = {x["t"]: x for x in c["tabla"]}
    # al corte
    # ponytail: DATEDIF(desembolso; corte) es exacto con corte a fin de un mes de 31 días; con corte a 30-jun y desembolso
    # el día 31, la cuota que vence el mismo corte queda como devengo completo (fracción 1). Contar vencimientos si hace falta.
    c["M"] = _meses(d0, corte)
    c["k"] = min(n, c["M"] // m)
    c["frac"] = _frac(d0, int(c["k"]), m, n, corte)
    c["cap_c"] = T[int(c["k"])]["fin"]
    c["acc_nom"] = c["cap_c"] * c["i"] * c["frac"]
    c["ca_k"] = T[int(c["k"])]["ca_fin"]
    c["acc_tie"] = c["ca_k"] * c["tie"] * c["frac"]
    c["ca_tot"] = c["ca_k"] + c["acc_tie"]
    # al inicio del ejercicio
    c["Mi"] = -1 if d0 > inicio else _meses(d0, inicio)
    c["kp"] = 0 if c["Mi"] < 0 else min(n, c["Mi"] // m)
    c["frac_i"] = 0 if (c["Mi"] < 0 or c["kp"] >= n) else _frac(d0, int(c["kp"]), m, n, inicio)
    c["cap_i"] = 0 if c["Mi"] < 0 else T[int(c["kp"])]["fin"]
    c["acc_nom_i"] = c["cap_i"] * c["i"] * c["frac_i"]
    c["ca_i"] = 0 if c["Mi"] < 0 else T[int(c["kp"])]["ca_fin"]
    c["acc_tie_i"] = c["ca_i"] * c["tie"] * c["frac_i"]
    c["ca_tot_i"] = c["ca_i"] + c["acc_tie_i"]
    c["alta"] = c["neto"] if c["Mi"] < 0 else 0
    rango = lambda key: sum(x[key] for x in c["tabla"] if c["kp"] < x["t"] <= c["k"])
    c["pagos"] = rango("pago")
    c["int_anio"] = rango("int_nom") + c["acc_nom"] - c["acc_nom_i"]
    c["gasto_tie"] = rango("int_tie") + c["acc_tie"] - c["acc_tie_i"]
    c["comprobacion"] = c["ca_tot_i"] + c["alta"] + c["gasto_tie"] - c["pagos"] - c["ca_tot"]
    # comisiones
    if c["trat_comisiones"]:
        c["trat"] = c["trat_comisiones"]
    elif com == 0:
        c["trat"] = "Sin comisiones"
    elif abs(c["saldo_reg"] - c["cap_c"]) <= 0.01:
        c["trat"] = "Gasto (inferido)"
    else:
        c["trat"] = "TIE"
    c["amort_costos"] = c["gasto_tie"] - c["int_anio"]
    c["por_amortizar"] = c["cap_c"] - c["ca_k"]
    c["efecto_gasto"] = c["por_amortizar"] if c["trat"].startswith("Gasto") else 0
    # clasificación (sin covenant)
    c["kq"] = min(c["k"] + 12 / m, n)
    c["cap_12"] = T[int(c["kq"])]["fin"]
    c["cp_venc"] = min(c["cap_c"] - c["cap_12"] + c["acc_tie"], c["ca_tot"])
    return c


_CONCL_BLOQ = "Dato insuficiente: conclusión bloqueada"
_CONCL_SUST = "Sustancial: baja del pasivo original y reconocimiento de uno nuevo (3.3.2)"
_CONCL_NO = "No sustancial: el pasivo continúa; costos y comisiones se amortizan (B3.3.6A)"


def _prueba10(c: dict, filas: list) -> list:
    """Prueba del 10 % (NIIF 9 3.3.2 y B3.3.6): valor presente de los flujos descontado a la TIE original.

    Sin fecha de la modificación, sin flujos originales restantes o sin flujos modificados la prueba NO concluye
    (resultado vacío). Devuelve las filas de la cédula 14 con el valor presente de cada flujo.
    """
    fm, tie = c["fecha_modificacion"], c["tie_anual"]
    c["n_orig"] = sum(1 for x in filas if x["escenario"] == "Original")
    c["n_mod"] = sum(1 for x in filas if x["escenario"] == "Modificado")
    c["com_mod_n"] = c["comision_modificacion"] or 0
    detalle = []
    for x in filas:
        anios = None if fm is None else (x["fecha"] - fm).days / 365
        detalle.append({**x, "anios": anios, "tie": tie, "vp": None if anios is None else x["importe"] / (1 + tie) ** anios})
    suma_vp = lambda e: sum(x["vp"] for x in detalle if x["escenario"] == e and x["vp"] is not None)
    c["vp_orig"], c["vp_mod"] = suma_vp("Original"), suma_vp("Modificado")
    if fm is None or not c["n_orig"] or not c["n_mod"] or c["vp_orig"] <= 0:
        c["vp_nuevo"] = c["dif_vp"] = c["pct_vp"] = None
        c["sustancial"], c["conclusion"] = "", _CONCL_BLOQ
        return detalle
    c["vp_nuevo"] = c["vp_mod"] + c["com_mod_n"]
    c["dif_vp"] = c["vp_nuevo"] - c["vp_orig"]
    c["pct_vp"] = c["dif_vp"] / c["vp_orig"]
    c["sustancial"] = "Sí" if abs(c["pct_vp"]) >= 0.10 else "No"
    c["conclusion"] = _CONCL_SUST if c["sustancial"] == "Sí" else _CONCL_NO
    return detalle


def _dif(x) -> bool:
    """Diferencia mayor que un centavo (los datos del cliente vienen redondeados a centavos)."""
    return x is not None and abs(round(x, 2)) > 0.01


def _num_param(p: dict, k: str):
    v = p.get(k)
    if v is None or str(v).strip() == "":
        return None
    x = a_num(v)
    if x is None or (x < 0 and k not in PARAM_NEGATIVOS):
        raise ValueError(f"{ETIQUETAS_PARAM[k]}: indique un número{'' if k in PARAM_NEGATIVOS else ' no negativo'}.")
    return x


def _ratio(num, den):
    return None if num is None or den is None or den <= 0 else num / den


def ejecutar(datasets: dict, parametros: dict, corte: str) -> dict:
    p = {**PARAMETROS, **{k: v for k, v in (parametros or {}).items() if v is not None and v != ""}}
    corte_a = a_fecha(corte)
    if corte_a is None:
        raise ValueError("Indique la fecha de corte del encargo.")
    for k in _NUM_PARAM:
        p[k] = _num_param(p, k)
    base = str(p.get("baseCobertura") or "EBITDA").strip().upper()
    if base not in ("EBITDA", "EBIT"):
        raise ValueError("Base de la cobertura de intereses: elija «EBITDA» o «EBIT».")
    p["baseCobertura"] = base
    # (B) El contrato manda: solo con la definición contractual del DSCR la herramienta concluye sobre el covenant.
    p["defDSCR"] = str(p.get("defDSCR") or "").strip() or None
    if p["servicioDSCRContrato"] is not None and not p["defDSCR"]:
        raise ValueError("Informó el servicio de la deuda del DSCR según el contrato sin la definición contractual del DSCR: "
                         "transcriba la definición del contrato (numerador ÷ denominador) o deje ambos vacíos.")
    pymes = es_pymes(p)
    if not datasets.get("prestamos"):
        raise ValueError("Cargue el anexo de préstamos y obligaciones financieras.")
    inicio = _edate(corte_a, -12)
    probs = []
    cs = [c for c in (_prestamo(f, corte_a, inicio, probs) for f in datasets["prestamos"]) if c]
    if not cs:
        raise ValueError("Ningún préstamo fue desembolsado hasta la fecha de corte.")
    vistos = set()
    for c in cs:
        if c["id"].lower() in vistos:
            raise ValueError(f"Operación repetida: {c['id']}. Cada préstamo debe tener un código único.")
        vistos.add(c["id"].lower())

    # (A) prueba del 10 % (NIIF 9 3.3.2 y B3.3.6): anexo opcional de flujos de la adenda
    por_prestamo = {c["id"].lower(): [] for c in cs}
    for f in datasets.get("flujos") or []:
        pid = str(f.get("id", "") or "").strip()
        esc, fch, imp = _escenario(f.get("escenario")), a_fecha(f.get("fecha")), a_num(f.get("importe"))
        if pid.lower() not in por_prestamo:
            probs.append(problema("FLUJOS_SIN_PRESTAMO", f"Flujo de la fila {f.get('_row')}: la operación «{pid or '(sin código)'}» no está en el "
                                                         "anexo de préstamos al corte; no se usó en la prueba del 10 %."))
            continue
        if esc in ("", "?") or fch is None or imp is None:
            probs.append(problema("FLUJO_INCOMPLETO", f"{pid}: el flujo de la fila {f.get('_row')} no tiene escenario (original / modificado), "
                                                      "fecha o importe legibles; no se usó en la prueba del 10 %."))
            continue
        por_prestamo[pid.lower()].append({"id": pid, "escenario": esc, "fecha": fch, "importe": imp, "_row": f.get("_row")})
    flujos_det = []
    for c in cs:
        fl = sorted(por_prestamo[c["id"].lower()], key=lambda x: (x["escenario"], x["fecha"]))
        c["prueba10"] = "Sí" if (c["modificado"] == "Sí" or c["fecha_modificacion"] is not None or fl) else "No"
        if c["prueba10"] == "No":
            continue
        flujos_det += _prueba10(c, fl)
    mods = [c for c in cs if c["prueba10"] == "Sí"]

    # endeudamiento (analítica, cédula 12)
    deuda = sum(c["ca_tot"] for c in cs)
    gasto = sum(c["gasto_tie"] for c in cs)
    servicio = sum(c["pagos"] for c in cs)
    base_cob = p["ebit"] if base == "EBIT" else p["ebitda"]
    analitico = "Analítica de auditoría (no es un requisito NIIF)"
    dscr_contractual = p["defDSCR"] is not None
    servicio_dscr = p["servicioDSCRContrato"] if p["servicioDSCRContrato"] is not None else servicio
    defs = [("Deuda / activos", deuda, p["totalActivos"], p["limDeudaActivos"], "Máximo", analitico),
            ("Deuda / patrimonio", deuda, p["patrimonio"], p["limDeudaPatrimonio"], "Máximo", analitico),
            ("Deuda / EBITDA", deuda, p["ebitda"], p["limDeudaEbitda"], "Máximo", analitico),
            ("Cobertura de intereses", base_cob, gasto, p["limCobertura"], "Mínimo", analitico),
            ("DSCR", p["efectivoServicioDeuda"], servicio_dscr, p["limDSCR"], "Mínimo",
             p["defDSCR"] if dscr_contractual else DSCR_ANALITICO)]
    ratios = {}
    for nombre, num, den, lim, tipo, definicion in defs:
        r = _ratio(num, den)
        cumple = "" if r is None or lim is None else ("Sí" if (r <= lim if tipo == "Máximo" else r >= lim) else "No")
        if nombre == "DSCR" and not dscr_contractual:
            cumple = ""      # sin definición contractual el DSCR no concluye incumplimiento (decisión del socio)
        ratios[nombre] = {"num": num, "den": den, "ratio": r, "lim": lim, "tipo": tipo, "cumple": cumple, "definicion": definicion}
        if cumple == "No":
            probs.append(problema("ENDEUDAMIENTO_SOBRE_LIMITE", f"{nombre}: {r:.2f} veces frente al límite {tipo.lower()} de {lim:g} veces. ".replace(".", ",", 2) + (
                                  "Analítica de auditoría (no es un requisito NIIF): revise el efecto en covenants, empresa en marcha (NIA 570) y revelaciones (NIIF 7 18–19).")))
        elif lim is not None and r is None:
            probs.append(problema("RATIO_NO_CALCULABLE", f"{nombre}: hay límite pactado pero faltan datos de la entidad o el denominador no es positivo; no se evaluó."))
    d_ = ratios["DSCR"]
    if not dscr_contractual and d_["ratio"] is not None:
        probs.append(problema("DSCR_ANALITICO_SIN_DEFINICION",
                              f"{DSCR_ANALITICO}: {d_['ratio']:.2f}".replace(".", ",") + " veces (efectivo disponible para el servicio de la deuda "
                              f"÷ servicio de la deuda del ejercicio según las tablas {_m(servicio_dscr)})"
                              + (f", frente al límite mínimo de {d_['lim']:g} veces".replace(".", ",") if d_["lim"] is not None else "") +
                              ". No se informó la definición contractual del DSCR, así que esta métrica NO concluye incumplimiento del covenant "
                              "ni reclasifica la deuda: es solo un indicador para el auditor. Transcriba del contrato la definición del DSCR "
                              "(numerador y denominador) en los parámetros; el contrato manda sobre cualquier definición contable."))

    # covenants y clasificación
    lim12 = _edate(corte_a, 12)
    for c in cs:
        rt = ratios.get(c["covenant"]) if c["covenant"] else None
        c["cov_ratio"], c["cov_lim"], c["cov_tipo"], c["cov_cumple"], c["cov_def"] = (
            (rt["ratio"], rt["lim"], rt["tipo"], rt["cumple"], rt["definicion"]) if rt else (None, None, None, "", None))
        c["declarado"] = c["incumplido"] or "No"
        c["incump"] = "Sí" if c["declarado"] == "Sí" or c["cov_cumple"] == "No" else "No"
        fd, gh = c["fecha_dispensa"], c["gracia_hasta"]
        c["disp_valida"] = "Sí" if fd is not None and fd <= corte_a and (gh is None or gh >= lim12) else "No"
        # NIC 1 72B: solo inciden en la clasificación las condiciones pactadas que deben cumplirse al cierre o antes.
        # Las que se miden después del corte no reclasifican; exigen la revelación del párrafo 76ZA.
        c["cov_futuro"] = "Sí" if c["fecha_covenant"] is not None and c["fecha_covenant"] > corte_a else "No"
        c["exigible"] = "Sí" if c["incump"] == "Sí" and c["disp_valida"] == "No" and c["cov_futuro"] == "No" else "No"
        c["cp"] = c["ca_tot"] if c["exigible"] == "Sí" else c["cp_venc"]
        c["lp"] = c["ca_tot"] - c["cp"]
        c["reg_tot"] = c["saldo_reg"] + (c["int_reg"] or 0)
        c["ajuste"] = c["ca_tot"] - c["reg_tot"]

    # problemas
    for c in cs:
        pid = c["id"]
        c["explicado"] = c["por_amortizar"] if c["trat"] == "TIE" else 0
        c["dif_conf"] = None if c["confirmado"] is None else c["confirmado"] - c["saldo_reg"] - c["explicado"]
        if _dif(c["dif_conf"]):
            probs.append(problema("CONFIRMACION_DIFERENCIA", f"{pid}: el banco confirma {_m(c['confirmado'])} de capital y el cliente registra {_m(c['saldo_reg'])}; diferencia no explicada por costos por amortizar {_m(c['dif_conf'])} (NIA 505).",
                                  c["dif_conf"]))
        if c["confirmado"] is not None and _dif(c["confirmado"] - c["cap_c"]):
            probs.append(problema("CONFIRMACION_VS_TABLA", f"{pid}: el saldo confirmado {_m(c['confirmado'])} no coincide con el capital de la tabla contractual {_m(c['cap_c'])}; indague prepagos, cuotas vencidas o refinanciaciones ({'PYMES 11.37; la prueba del 10 % de la NIIF 9 B3.3.6 por analogía, 10.6' if pymes else 'NIIF 9 3.3.2 y B3.3.6'}).",
                                  c["confirmado"] - c["cap_c"]))
        no_reg = c["acc_nom"] - (c["int_reg"] or 0)
        if no_reg > 0.01 and _dif(no_reg):
            probs.append(problema("INTERES_DEVENGADO_NO_REGISTRADO", f"{pid}: interés devengado desde el último vencimiento {_m(c['acc_nom'])} y registrado {_m(c['int_reg'] or 0)} (devengo, {'PYMES 11.15–11.16' if pymes else 'NIIF 9 4.2.1 y Apéndice A'}).", no_reg))
        if _dif(c["efecto_gasto"]):
            probs.append(problema("COMISIONES_A_GASTO", f"{pid}: las comisiones de {_m(c['com'])} se llevaron a gasto; forman parte de la TIE ({'PYMES 11.13 y 11.15–11.20: aunque el cliente use la tasa nominal, con comisiones materiales aplica el interés efectivo' if pymes else 'NIIF 9 5.1.1 y Apéndice A'}). Costo pendiente de amortizar al corte {_m(c['por_amortizar'])}.",
                                  -c["efecto_gasto"]))
        if c["gasto_reg"] is not None and _dif(c["gasto_tie"] - c["gasto_reg"]):
            probs.append(problema("GASTO_FINANCIERO_DIFERENCIA", f"{pid}: gasto financiero a la TIE {_m(c['gasto_tie'])} vs registrado {_m(c['gasto_reg'])}.", c["gasto_tie"] - c["gasto_reg"]))
        if c["pagos_anio"] is not None and _dif(c["pagos"] - c["pagos_anio"]):
            probs.append(problema("PAGOS_DIFERENCIA", f"{pid}: pagos del año según la tabla {_m(c['pagos'])} vs informados {_m(c['pagos_anio'])}; indague cuotas impagas o prepagos.", c["pagos"] - c["pagos_anio"]))
        if c["exigible"] == "Sí" and c["lp"] == 0 and _dif(c["cp"] - c["cp_venc"]):
            probs.append(problema("COVENANT_SIN_DISPENSA", f"{pid}: covenant «{c['covenant'] or 'del contrato'}» incumplido al corte sin dispensa obtenida hasta el corte con gracia ≥ 12 meses: toda la deuda es corriente ({'PYMES 4.7 d) (derecho incondicional); la NIC 1 72B/74/75 se usa por analogía (jerarquía 10.6), como juicio del auditor' if pymes else 'NIC 1 74–75'}).",
                                  c["cp"] - c["cp_venc"]))
        if c["incump"] == "Sí" and c["fecha_dispensa"] is not None and c["fecha_dispensa"] > corte_a:
            probs.append(problema("DISPENSA_POSTERIOR", f"{pid}: la dispensa del {c['fecha_dispensa'].isoformat()} es posterior al corte: no cambia la clasificación ({'4.7' if pymes else 'NIC 1 74'}); revele como hecho posterior no ajustante ({'Sección 32' if pymes else 'NIC 1 76 b)–c), NIC 10'})."))
        if c["cov_futuro"] == "Sí":
            probs.append(problema("COVENANT_POSTERIOR_AL_CORTE", f"{pid}: la condición pactada «{c['covenant'] or 'del contrato'}» se mide el "
                                  f"{c['fecha_covenant'].isoformat()}, después del corte: no incide en la clasificación al cierre y la deuda no se "
                                  f"reclasifica a corriente ({'PYMES 4.7 d); la NIC 1 72B se usa por analogía (jerarquía 10.6)' if pymes else 'NIC 1 72B'})"
                                  + (", pese al incumplimiento identificado" if c["incump"] == "Sí" else "") + ". Revele en las notas la información que permita "
                                  "a los usuarios entender el riesgo de que el pasivo pase a ser reembolsable dentro de los doce meses: el valor en libros, "
                                  f"la naturaleza y la fecha de la condición y los hechos que indiquen dificultad para cumplirla "
                                  f"({'NIC 1 76ZA por analogía (10.6)' if pymes else 'NIC 1 76ZA'}).", c["lp"]))
        elif c["covenant"] and c["fecha_covenant"] is None:
            probs.append(problema("COVENANT_SIN_FECHA_MEDICION", f"{pid}: covenant «{c['covenant']}» sin fecha de medición. Solo afectan la clasificación "
                                  f"las condiciones que deben cumplirse al cierre o antes ({'NIC 1 72B por analogía (PYMES 10.6)' if pymes else 'NIC 1 72B'}); "
                                  "se mantuvo el tratamiento actual (el incumplimiento reclasifica a corriente). Informe la fecha de medición del contrato."))
        if c["covenant"] == "DSCR" and not dscr_contractual and c["declarado"] != "Sí":
            probs.append(problema("COVENANT_DSCR_SIN_DEFINICION", f"{pid}: el covenant pactado es el DSCR y no se informó su definición contractual. "
                                  f"El «{DSCR_ANALITICO}» es solo un indicador para el auditor: no concluye incumplimiento del covenant ni "
                                  f"reclasifica la deuda a corriente ({'PYMES 4.7 d)' if pymes else 'NIC 1 74–75'}). Revise el contrato de préstamo "
                                  "y transcriba en los parámetros la definición del DSCR (numerador y denominador) y, si el contrato lo define "
                                  "distinto del servicio de la deuda de las tablas, su denominador."))
        elif c["covenant"] and c["cov_cumple"] == "" and c["declarado"] != "Sí":
            probs.append(problema("COVENANT_SIN_EVALUAR", f"{pid}: covenant «{c['covenant']}» sin datos o límite de la entidad para evaluarlo; complete los parámetros."))
        if c["prueba10"] == "Sí":
            analogia = (" En la NIIF para las PYMES esta prueba del 10 % no existe: la Sección 11 (11.37) exige condiciones «sustancialmente "
                        "diferentes» sin umbral cuantitativo, y el umbral del 10 % de la NIIF 9 B3.3.6 se aplica por analogía (jerarquía 10.6), "
                        "como juicio del auditor.") if pymes else ""
            if c["sustancial"] == "":
                falta = [] if c["fecha_modificacion"] is not None else ["la fecha de la modificación"]
                falta += ([] if c["n_orig"] else ["los flujos contractuales originales que restaban a esa fecha"])
                falta += ([] if c["n_mod"] else ["los flujos de la adenda (fecha e importe de cada pago)"])
                lista = " y ".join([", ".join(falta[:-1]), falta[-1]]).strip(" ,") if falta else "el anexo de flujos de la modificación"
                probs.append(problema("MODIFICACION_DATO_INSUFICIENTE", f"{pid}: dato insuficiente: conclusión bloqueada. No se puede resolver la "
                                      f"prueba del 10 % ({'PYMES 11.37; NIIF 9 3.3.2 y B3.3.6 por analogía (10.6)' if pymes else 'NIIF 9 3.3.2 y B3.3.6'}) "
                                      f"porque falta{'n' if len(falta) > 1 else ''} {lista}. "
                                      "Papel que hay que revisar: la adenda del préstamo con su tabla de flujos; cargue en el anexo de flujos una fila "
                                      "por pago, con escenario «Original» o «Modificado», fecha e importe. Mientras falte, la herramienta no concluye "
                                      "si la modificación es sustancial: no se presume «no sustancial»." + analogia))
            else:
                cual = "sustancialmente diferentes" if c["sustancial"] == "Sí" else "no sustancialmente diferentes"
                accion = ("Dé de baja el pasivo original y reconozca uno nuevo a valor razonable; la diferencia va a resultados (3.3.3) y los costos "
                          "y comisiones se reconocen en la pérdida o ganancia de la extinción (B3.3.6A)." if c["sustancial"] == "Sí" else
                          "El pasivo continúa: ajuste el importe en libros por los costos y comisiones y amortícelos en la vida restante (B3.3.6A).")
                pct = f"{abs(c['pct_vp']) * 100:.2f}".replace(".", ",")
                tie_txt = f"{c['tie_anual'] * 100:.4f}".replace(".", ",")
                probs.append(problema("MODIFICACION_SUSTANCIAL" if c["sustancial"] == "Sí" else "MODIFICACION_NO_SUSTANCIAL",
                                      f"{pid}: las condiciones de la adenda del {c['fecha_modificacion'].isoformat()} son {cual}: el valor presente de "
                                      f"las nuevas condiciones {_m(c['vp_nuevo'])} difiere en {pct} % ({_m(c['dif_vp'])}) del valor presente de los "
                                      f"flujos originales restantes {_m(c['vp_orig'])}, descontados a la tasa de interés efectiva original "
                                      f"({tie_txt} %). {accion} La herramienta no remide el pasivo después de la modificación: las cédulas 04 a 13 "
                                      f"siguen el contrato original.{analogia}", c["dif_vp"]))
            if c["sustancial"] != "" and c["comision_modificacion"] is None:
                probs.append(problema("MODIFICACION_SIN_COMISIONES", f"{pid}: no se informaron las comisiones pagadas al prestamista netas de las "
                                      "recibidas por la modificación (NIIF 9 B3.3.6), así que la prueba se resolvió solo con los flujos. Papel que hay "
                                      "que revisar: la liquidación de la adenda; si hubo comisiones, infórmelas y vuelva a correr la prueba."))
        if c["cp_reg"] is not None and _dif(c["cp"] - c["cp_reg"]):
            probs.append(problema("CLASIFICACION_CP_LP", f"{pid}: porción corriente auditada {_m(c['cp'])} vs registrada {_m(c['cp_reg'])} ({'4.7' if pymes else 'NIC 1 69–76'}).", c["cp"] - c["cp_reg"]))
        if _dif(c["ajuste"]):
            probs.append(problema("PASIVO_DIFERENCIA", f"{pid}: costo amortizado con intereses devengados {_m(c['ca_tot'])} vs registrado (capital + intereses) {_m(c['reg_tot'])}.", c["ajuste"]))
        # NIIF 7 18–19 / PYMES 11.47: impagos de principal o intereses e infracciones de otras cláusulas no
        # subsanados al cierre se revelan aunque no cambien la clasificación.
        impago = c["pagos"] - c["pagos_anio"] if c["pagos_anio"] is not None else 0
        if c["incump"] == "Sí" or _dif(impago) and impago > 0:
            motivos = (["incumplimiento de la condición pactada «" + (c["covenant"] or "del contrato") + "»"] if c["incump"] == "Sí" else []) + \
                      ([f"impago de principal o intereses por {_m(impago)} (pagos de la tabla {_m(c['pagos'])} vs informados {_m(c['pagos_anio'])})"]
                       if _dif(impago) and impago > 0 else [])
            probs.append(problema("REVELACION_INCUMPLIMIENTO", f"{pid}: {' y '.join(motivos)} sin subsanar al cierre. Revele el detalle del "
                                  f"incumplimiento, el importe en libros del préstamo ({_m(c['ca_tot'])}) y si se subsanó o se renegociaron las "
                                  f"condiciones antes de la autorización de los estados financieros ({'PYMES 11.47' if pymes else 'NIIF 7 18–19'}).",
                                  c["ca_tot"]))

    T = lambda k: sum(c[k] for c in cs)
    gasto_con_reg = sum(c["gasto_tie"] - c["gasto_reg"] for c in cs if c["gasto_reg"] is not None)
    totales = {"pasivoRegistrado": T("reg_tot"), "pasivo": T("ca_tot"), "ajuste": T("ca_tot") - T("reg_tot"),
               "capitalContractual": T("cap_c"), "interesesDevengados": T("acc_nom"), "interesesRegistrados": sum(c["int_reg"] or 0 for c in cs),
               "corriente": T("cp"), "noCorriente": T("lp"), "reclasificacionCovenant": T("cp") - T("cp_venc"),
               "gastoFinanciero": T("gasto_tie"), "diferenciaGasto": gasto_con_reg, "comisionesPorAmortizar": T("por_amortizar")}
    etiquetas = {"pasivoRegistrado": "Obligaciones financieras registradas (capital + intereses)", "pasivo": "Costo amortizado recalculado (con interés devengado)",
                 "ajuste": "Ajuste propuesto al pasivo", "capitalContractual": "Capital contractual según tablas",
                 "interesesDevengados": "Interés contractual devengado al corte", "interesesRegistrados": "Intereses por pagar registrados",
                 "corriente": "Pasivo corriente auditado", "noCorriente": "Pasivo no corriente auditado",
                 "reclasificacionCovenant": "Reclasificación a corriente por covenants", "gastoFinanciero": "Gasto financiero del ejercicio (TIE)",
                 "diferenciaGasto": "Diferencia de gasto financiero (préstamos con gasto registrado)", "comisionesPorAmortizar": "Costos de transacción por amortizar al corte"}
    rows = [{"id": c["id"], "banco": c["banco"], "desembolso": c["desembolso"].isoformat(), "sistema": c["sistema"],
             "capital": r2(c["cap_c"]), "costo_amortizado": r2(c["ca_tot"]), "registrado": r2(c["reg_tot"]), "ajuste": r2(c["ajuste"]),
             "corriente": r2(c["cp"]), "tie_anual": f"{c['tie_anual'] * 100:.4f}", "_row": c["_row"]} for c in cs]
    tabla = [x for c in cs for x in c["tabla"]]
    flujos = [{**x, "fecha": x["fecha"].isoformat()} for x in flujos_det]
    ids_mod = [c["id"] for c in mods]
    for c in cs:
        for k in ("desembolso", "fecha_dispensa", "gracia_hasta", "fecha_covenant", "fecha_modificacion"):
            c[k] = c[k].isoformat() if c[k] else None
        del c["tabla"]
    detalle = {"prestamos": cs, "tabla": tabla, "ratios": ratios, "deuda": deuda, "gasto": gasto, "servicio": servicio,
               "servicio_dscr": servicio_dscr, "dscr_contractual": dscr_contractual, "flujos": flujos, "ids_mod": ids_mod,
               "parametros": p, "pymes": pymes, "edicion": edicion_pymes(p) if pymes else "", "corte": corte_a.isoformat(),
               "inicio": inicio.isoformat(), "totales": totales}
    return {"engine": VERSION, "rows": rows, "totals": {k: r2(v) for k, v in totales.items()}, "labels": etiquetas,
            "primary": "ajuste", "exceptions": probs, "schedule": [], "detalle": detalle}


# --- cédulas con fórmulas -------------------------------------------------------------

CEDULAS = [
    ("01_Resumen", "Resumen"), ("02_Parametros", "Parámetros"), ("03_Prestamos", "Universo de préstamos"),
    ("04_Condiciones_TIE", "Condiciones y tasa de interés efectiva"), ("05_Tabla_amortizacion", "Tabla de amortización"),
    ("06_Costo_amortizado", "Costo amortizado al corte y del ejercicio"), ("07_Comisiones", "Comisiones y costos de transacción"),
    ("08_Intereses", "Recálculo de intereses"), ("09_Confirmacion", "Confirmación bancaria y pagos"),
    ("10_Covenants", "Covenants y dispensas"), ("11_Clasificacion", "Clasificación corriente / no corriente"),
    ("12_Endeudamiento", "Endeudamiento y ratios de covenants"), ("13_Conciliacion", "Conciliación y ajuste"),
    ("14_Flujos_modificacion", "Flujos de la modificación (adenda)"), ("15_Prueba_10pct", "Prueba del 10 % (NIIF 9 3.3.2 y B3.3.6)"),
    ("16_Problemas", "Problemas encontrados"),
]
# Panel del dashboard (formato en graficos.py): capital registrado de los préstamos evaluados; pasivo recalculado al costo
# amortizado frente al registrado (capital + intereses); composición del pasivo recalculado por operación y deuda por banco.
PANEL = {
    "poblacion":   {"rotulo": "Capital registrado evaluado", "hoja": "13_Conciliacion", "col": "Capital registrado"},
    "recalculado": {"rotulo": "Costo amortizado recalculado", "total": "pasivo"},
    "registrado":  {"rotulo": "Pasivo registrado", "total": "pasivoRegistrado"},
    "composicion": {"rotulo": "Costo amortizado por operación", "hoja": "13_Conciliacion", "etiqueta": "Operación",
                    "valor": "Costo amortizado auditado"},
    "distribucion": {"rotulo": "Capital registrado por banco", "hoja": "09_Confirmacion", "etiqueta": "Banco", "valor": "Capital registrado"},
}

P = ref("02_Parametros")
PR, CO, TA, CA, CM, IN, CV, CL, EN, FL = (ref(n) for n in ("03_Prestamos", "04_Condiciones_TIE", "05_Tabla_amortizacion", "06_Costo_amortizado",
                                                           "07_Comisiones", "08_Intereses", "10_Covenants", "11_Clasificacion", "12_Endeudamiento",
                                                           "14_Flujos_modificacion"))
PAR = {k: FILA0 + i for i, k in enumerate(["corte", "inicio", "marco"] + list(PARAMETROS))}
CORTE, INICIO = f"{P}$B${PAR['corte']}", f"{P}$B${PAR['inicio']}"
DEFD, SDC = f"{P}$B${PAR['defDSCR']}", f"{P}$B${PAR['servicioDSCRContrato']}"
FR = FILA0 + 3  # primera fila de ratios en 12_Endeudamiento


def _x(key: str, r: int) -> str:
    return f"{PR}{COL[key]}{r}"


def _opt(key: str, r: int, v):
    return fx(f'IF({_x(key, r)}="","",{_x(key, r)})', v)


def _pp(k: str) -> str:
    c = f"{P}$B${PAR[k]}"
    return f'IF({c}="","",{c})'


def hojas(res: dict) -> list[dict]:
    d = res["detalle"]
    cs, p, pymes, tab = d["prestamos"], d["parametros"], d["pymes"], d["tabla"]
    N, nt = len(cs), max(len(tab), 1)
    rng = lambda col: f"{TA}${col}${FILA0}:${col}${FILA0 + nt - 1}"
    TA_A, TA_B = rng("A"), rng("B")
    en = lambda col, r, t: f"SUMIFS({rng(col)},{TA_A},A{r},{TA_B},{t})"
    entre = lambda col, r, a, b: f'SUMIFS({rng(col)},{TA_A},A{r},{TA_B},">"&{a},{TA_B},"<="&{b})'
    niif18 = d["corte"] >= "2027-01-01"
    marco = (f"NIIF para las PYMES {d['edicion']} · Sección 11 (costo amortizado, 11.13–11.20) y Sección 4 (4.7 clasificación)" if pymes else
             ("NIIF completas · NIIF 9 (5.1.1, 4.2.1, 5.3.1 y Apéndice A) y NIIF 18 párr. 101 y B99–B106 para la presentación (ejercicios desde 2027; covenants: B100, B102–B103, B105–B106)" if niif18 else
              "NIIF completas · NIIF 9 (5.1.1, 4.2.1, 5.3.1 y Apéndice A) y NIC 1 69–76 (modificaciones 2020/2022, vigentes desde 2024)"))
    sust = {"totalActivos": "Estados financieros al corte", "patrimonio": "Estados financieros al corte (admite negativo)",
            "ebitda": "Estado de resultados; use la definición del contrato, que manda sobre cualquier otra", "ebit": "Estado de resultados",
            "efectivoServicioDeuda": "Use la definición del contrato de préstamo, que manda sobre cualquier otra", "baseCobertura": "EBITDA o EBIT, según el contrato",
            "limDeudaActivos": "Contrato de préstamo", "limDeudaPatrimonio": "Contrato de préstamo", "limDeudaEbitda": "Contrato de préstamo",
            "limCobertura": "Contrato de préstamo", "limDSCR": "Contrato de préstamo",
            "defDSCR": ("Transcriba la definición del contrato (numerador ÷ denominador). El contrato manda: sin esta definición el DSCR se muestra "
                        f"como «{DSCR_ANALITICO}» y no concluye incumplimiento del covenant"),
            "servicioDSCRContrato": "Contrato de préstamo; vacío = servicio de la deuda del ejercicio según las tablas (cédula 12)"}
    parametros = [["Fecha de corte", d["corte"], "Ficha del encargo"],
                  ["Inicio del ejercicio (corte − 12 meses)", d["inicio"], "Base del gasto financiero del ejercicio"],
                  ["Marco y ruta de cálculo", marco, "El modelo de costo amortizado es el mismo en ambos marcos; cambian las citas"]]
    parametros += [[ETIQUETAS_PARAM[k], p[k] if k in _TXT_PARAM else (None if p[k] is None else float(p[k])), sust[k]] for k in PARAMETROS]

    fmt03 = {"text": "t", "number": "n", "date": "d"}
    cols03 = [[cc["label"], fmt03[cc["type"]]] for cc in _PRESTAMOS]
    universo = [[c.get(k) if c.get(k) != "" else None for k in COL] for c in cs]

    fila_c = {c["id"]: FILA0 + i for i, c in enumerate(cs)}
    rango_t = {}
    for k, x in enumerate(tab):
        a, b = rango_t.get(x["id"], (FILA0 + k, FILA0 + k))
        rango_t[x["id"]] = (a, FILA0 + k)

    cond, cam, com, inte, conf, cov, cla, conc = [], [], [], [], [], [], [], []
    for c in cs:
        r = fila_c[c["id"]]
        a, b = rango_t[c["id"]]
        G, H, J, L = f"{CO}G{r}", f"{CO}H{r}", f"{CO}J{r}", f"{CO}L{r}"
        d0 = _x("desembolso", r)
        per = _x("periodicidad", r)
        cond.append([
            c["id"], fx(_x("sistema", r), c["sistema"]), fx(_x("monto", r), c["monto"]), fx(f"N({_x('comisiones', r)})", c["com"]),
            fx(f"C{r}-D{r}", c["neto"]), fx(_x("plazo", r), c["plazo"]),
            fx(f'IF({per}="Mensual",1,IF({per}="Trimestral",3,IF({per}="Semestral",6,12)))', c["m"]), fx(f"F{r}/G{r}", c["n"]),
            fx(_x("tasa", r), c["tasa"]), fx(f"I{r}/100*G{r}/12", c["i"]),
            fx(f'IF(B{r}="Francés",PMT(J{r},H{r},-C{r}),"")', c["cuota"]),
            fx(f"IRR({TA}I{a}:I{b},J{r})", c["tie"]), fx(f"(1+L{r})^(12/G{r})-1", c["tie_anual"]),
            fx(f"(1+J{r})^(12/G{r})-1", c["ef_contractual"]), fx(f"M{r}-N{r}", c["dif_tasa"]),
        ])
        frac = lambda k_: f"({{en}}-EDATE({d0},{k_}*{G}))/(EDATE({d0},({k_}+1)*{G})-EDATE({d0},{k_}*{G}))"
        cam.append([
            c["id"], fx(f'DATEDIF({d0},{CORTE},"m")', c["M"]), fx(f"MIN({H},INT(B{r}/{G}))", c["k"]),
            fx(f"IF(C{r}>={H},0,{frac(f'C{r}').format(en=CORTE)})", c["frac"]),
            fx(en("H", r, f"C{r}"), c["cap_c"]), fx(f"E{r}*{J}*D{r}", c["acc_nom"]), fx(en("M", r, f"C{r}"), c["ca_k"]),
            fx(f"G{r}*{L}*D{r}", c["acc_tie"]), fx(f"G{r}+H{r}", c["ca_tot"]),
            fx(f'IF({d0}>{INICIO},-1,DATEDIF({d0},{INICIO},"m"))', c["Mi"]), fx(f"IF(J{r}<0,0,MIN({H},INT(J{r}/{G})))", c["kp"]),
            fx(f"IF(OR(J{r}<0,K{r}>={H}),0,{frac(f'K{r}').format(en=INICIO)})", c["frac_i"]),
            fx(f"IF(J{r}<0,0,{en('H', r, f'K{r}')})", c["cap_i"]), fx(f"M{r}*{J}*L{r}", c["acc_nom_i"]),
            fx(f"IF(J{r}<0,0,{en('M', r, f'K{r}')})", c["ca_i"]), fx(f"O{r}*{L}*L{r}", c["acc_tie_i"]), fx(f"O{r}+P{r}", c["ca_tot_i"]),
            fx(f"IF(J{r}<0,{CO}E{r},0)", c["alta"]), fx(entre("D", r, f"K{r}", f"C{r}"), c["pagos"]),
            fx(f"{entre('F', r, f'K{r}', f'C{r}')}+F{r}-N{r}", c["int_anio"]), fx(f"{entre('K', r, f'K{r}', f'C{r}')}+H{r}-P{r}", c["gasto_tie"]),
            fx(f"Q{r}+R{r}+U{r}-S{r}-I{r}", c["comprobacion"]),
        ])
        trat = (f'IF({_x("trat_comisiones", r)}<>"",{_x("trat_comisiones", r)},IF(B{r}=0,"Sin comisiones",'
                f'IF(ABS(N({_x("saldo_reg", r)})-{CA}E{r})<=0.01,"Gasto (inferido)","TIE")))')
        com.append([c["id"], fx(f"{CO}D{r}", c["com"]), fx(trat, c["trat"]), fx(f"{CA}T{r}", c["int_anio"]), fx(f"{CA}U{r}", c["gasto_tie"]),
                    fx(f"E{r}-D{r}", c["amort_costos"]), fx(f"{CA}E{r}-{CA}G{r}", c["por_amortizar"]),
                    fx(f'IF(LEFT(C{r},5)="Gasto",G{r},0)', c["efecto_gasto"])])
        inte.append([c["id"], fx(f"{CO}I{r}", c["tasa"]), fx(f"{CO}M{r}", c["tie_anual"]), fx(f"{CA}T{r}", c["int_anio"]),
                     fx(f"{CA}U{r}", c["gasto_tie"]), _opt("gasto_reg", r, c["gasto_reg"]),
                     fx(f'IF(F{r}="","",E{r}-F{r})', None if c["gasto_reg"] is None else c["gasto_tie"] - c["gasto_reg"]),
                     fx(f"{CA}F{r}", c["acc_nom"]), fx(f"N({_x('int_reg', r)})", c["int_reg"] or 0),
                     fx(f"H{r}-I{r}", c["acc_nom"] - (c["int_reg"] or 0))])
        conf.append([c["id"], c["banco"], fx(f"{CA}E{r}", c["cap_c"]), _opt("confirmado", r, c["confirmado"]),
                     fx(f"N({_x('saldo_reg', r)})", c["saldo_reg"]), fx(f'IF({CM}C{r}="TIE",{CM}G{r},0)', c["explicado"]),
                     fx(f'IF(D{r}="","",D{r}-E{r}-F{r})', c["dif_conf"]),
                     fx(f'IF(D{r}="","",D{r}-C{r})', None if c["confirmado"] is None else c["confirmado"] - c["cap_c"]),
                     fx(f"{CA}S{r}", c["pagos"]), _opt("pagos_anio", r, c["pagos_anio"]),
                     fx(f'IF(J{r}="","",I{r}-J{r})', None if c["pagos_anio"] is None else c["pagos"] - c["pagos_anio"])])
        rr = f"{EN}$A${FR}:$A${FR + 4}"
        idx = lambda col: f'IF(B{r}="","",INDEX({EN}${col}${FR}:${col}${FR + 4},MATCH(B{r},{rr},0)))'
        fd, gh, fcv = _x("fecha_dispensa", r), _x("gracia_hasta", r), _x("fecha_covenant", r)
        cov.append([c["id"], _opt("covenant", r, c["covenant"] or None), fx(idx("D"), c["cov_ratio"]), fx(idx("E"), c["cov_lim"]),
                    fx(idx("F"), c["cov_tipo"]), fx(idx("G"), c["cov_cumple"] if c["covenant"] else None),
                    fx(f'IF({_x("incumplido", r)}="","No",{_x("incumplido", r)})', c["declarado"]),
                    fx(f'IF(OR(G{r}="Sí",F{r}="No"),"Sí","No")', c["incump"]), c["fecha_dispensa"], c["gracia_hasta"],
                    fx(f'IF(AND({fd}<>"",{fd}<={CORTE},OR({gh}="",{gh}>=EDATE({CORTE},12))),"Sí","No")', c["disp_valida"]),
                    fx(f'IF(AND(H{r}="Sí",K{r}="No",N{r}="No"),"Sí","No")', c["exigible"]), c["fecha_covenant"],
                    fx(f'IF(AND({fcv}<>"",{fcv}>{CORTE}),"Sí","No")', c["cov_futuro"]), fx(idx("H"), c["cov_def"])])
        cla.append([c["id"], fx(f"{CA}I{r}", c["ca_tot"]), fx(f"MIN({CA}C{r}+12/{G},{H})", c["kq"]), fx(en("H", r, f"C{r}"), c["cap_12"]),
                    fx(f"MIN({CA}E{r}-D{r}+{CA}H{r},B{r})", c["cp_venc"]), fx(f"{CV}L{r}", c["exigible"]), fx(f'IF(F{r}="Sí",B{r},E{r})', c["cp"]),
                    fx(f"B{r}-G{r}", c["lp"]), _opt("cp_reg", r, c["cp_reg"]),
                    fx(f'IF(I{r}="","",G{r}-I{r})', None if c["cp_reg"] is None else c["cp"] - c["cp_reg"])])
        conc.append([c["id"], fx(f"{CA}I{r}", c["ca_tot"]), fx(f"N({_x('saldo_reg', r)})", c["saldo_reg"]),
                     fx(f"N({_x('int_reg', r)})", c["int_reg"] or 0), fx(f"C{r}+D{r}", c["reg_tot"]), fx(f"B{r}-E{r}", c["ajuste"]),
                     fx(f"{CL}G{r}", c["cp"]), fx(f"{CL}H{r}", c["lp"]), fx(f"{CA}U{r}", c["gasto_tie"])])

    # 05 · tabla de amortización
    tabla = []
    for k, x in enumerate(tab):
        rr_, rc = FILA0 + k, fila_c[x["id"]]
        c = next(y for y in cs if y["id"] == x["id"])
        if x["t"] == 0:
            tabla.append([x["id"], 0, x["vence"], None, None, None, None, fx(f"{CO}C{rc}", x["fin"]), fx(f"-{CO}E{rc}", x["flujo"]),
                          None, None, None, fx(f"{CO}E{rc}", x["ca_fin"])])
            continue
        sis = f"{CO}B{rc}"
        pago = (f'IF({sis}="Francés",{CO}K{rc},IF({sis}="Alemán",{CO}C{rc}/{CO}H{rc}+F{rr_},'
                f'IF(B{rr_}<{CO}H{rc},F{rr_},F{rr_}+E{rr_})))')
        tabla.append([x["id"], x["t"], x["vence"], fx(pago, x["pago"]), fx(f"H{rr_ - 1}", x["ini"]), fx(f"E{rr_}*{CO}J{rc}", x["int_nom"]),
                      fx(f"D{rr_}-F{rr_}", x["cap"]), fx(f"E{rr_}-G{rr_}", x["fin"]), fx(f"D{rr_}", x["flujo"]),
                      fx(f"M{rr_ - 1}", x["ca_ini"]), fx(f"J{rr_}*{CO}L{rc}", x["int_tie"]), fx(f"D{rr_}-K{rr_}", x["amort"]),
                      fx(f"J{rr_}-L{rr_}", x["ca_fin"])])

    # 12 · endeudamiento
    fin = FILA0 + N - 1
    rt = d["ratios"]
    num_f = {"Deuda / activos": f"B{FILA0}", "Deuda / patrimonio": f"B{FILA0}", "Deuda / EBITDA": f"B{FILA0}",
             "Cobertura de intereses": f'IF({P}$B${PAR["baseCobertura"]}="EBIT",{_pp("ebit")},{_pp("ebitda")})', "DSCR": _pp("efectivoServicioDeuda")}
    den_f = {"Deuda / activos": _pp("totalActivos"), "Deuda / patrimonio": _pp("patrimonio"), "Deuda / EBITDA": _pp("ebitda"),
             "Cobertura de intereses": f"B{FILA0 + 1}", "DSCR": f'IF({SDC}="",B{FILA0 + 2},{SDC})'}
    lim_k = {"Deuda / activos": "limDeudaActivos", "Deuda / patrimonio": "limDeudaPatrimonio", "Deuda / EBITDA": "limDeudaEbitda",
             "Cobertura de intereses": "limCobertura", "DSCR": "limDSCR"}
    endeu = [["Deuda financiera auditada (costo amortizado)", fx(f"SUM({CA}I{FILA0}:I{fin})", d["deuda"]), None, None, None, None, None, None],
             ["Gasto financiero del ejercicio (TIE)", fx(f"SUM({CA}U{FILA0}:U{fin})", d["gasto"]), None, None, None, None, None, None],
             ["Servicio de la deuda del ejercicio (pagos)", fx(f"SUM({CA}S{FILA0}:S{fin})", d["servicio"]), None, None, None, None, None, None]]
    for j, nombre in enumerate(RATIOS):
        r, x = FR + j, rt[nombre]
        # (B) El DSCR solo concluye si el contrato lo define; sin definición es el «DSCR analítico de la firma» (indicador, no conclusión).
        puerta = f',{DEFD}=""' if nombre == "DSCR" else ""
        deff = fx(f'IF({DEFD}="","{DSCR_ANALITICO}",{DEFD})', x["definicion"]) if nombre == "DSCR" else x["definicion"]
        endeu.append([nombre, fx(num_f[nombre], x["num"]), fx(den_f[nombre], x["den"]),
                      fx(f'IF(OR(B{r}="",C{r}="",C{r}<=0),"",B{r}/C{r})', x["ratio"]), fx(_pp(lim_k[nombre]), x["lim"]), x["tipo"],
                      fx(f'IF(OR(D{r}="",E{r}=""{puerta}),"",IF(F{r}="Máximo",IF(D{r}<=E{r},"Sí","No"),IF(D{r}>=E{r},"Sí","No")))',
                         x["cumple"] or None), deff])

    # 14 y 15 · flujos de la adenda y prueba del 10 % (NIIF 9 3.3.2 y B3.3.6)
    fl = d["flujos"]
    nf = max(len(fl), 1)
    rf = lambda col: f"{FL}${col}${FILA0}:${col}${FILA0 + nf - 1}"
    flujos = []
    for k, x in enumerate(fl):
        r, rc = FILA0 + k, fila_c[x["id"]]
        fm = _x("fecha_modificacion", rc)
        flujos.append([x["id"], x["escenario"], x["fecha"], x["importe"],
                       fx(f'IF({fm}="","",(C{r}-{fm})/365)', x["anios"]), fx(f"{CO}M{rc}", x["tie"]),
                       fx(f'IF(E{r}="","",D{r}/(1+F{r})^E{r})', x["vp"])])
    prueba = []
    for c in (x for x in cs if x["id"] in d["ids_mod"]):
        r, rc = FILA0 + len(prueba), fila_c[c["id"]]
        fm, mdc = _x("fecha_modificacion", rc), _x("modificado", rc)
        cnt = lambda e: f'COUNTIFS({rf("A")},A{r},{rf("B")},"{e}")'
        vp = lambda e: f'SUMIFS({rf("G")},{rf("A")},A{r},{rf("B")},"{e}")'
        bloq = f'OR(E{r}=0,F{r}=0,{fm}="",G{r}<=0)'
        prueba.append([
            c["id"], fx(f'IF({mdc}="","No",{mdc})', c["modificado"]), c["fecha_modificacion"], fx(f"{CO}M{rc}", c["tie_anual"]),
            fx(cnt("Original"), c["n_orig"]), fx(cnt("Modificado"), c["n_mod"]), fx(vp("Original"), c["vp_orig"]),
            fx(vp("Modificado"), c["vp_mod"]), fx(f"N({_x('comision_modificacion', rc)})", c["com_mod_n"]),
            fx(f'IF({bloq},"",H{r}+I{r})', c["vp_nuevo"]), fx(f'IF(J{r}="","",J{r}-G{r})', c["dif_vp"]),
            fx(f'IF(J{r}="","",K{r}/G{r})', c["pct_vp"]),
            fx(f'IF(L{r}="","",IF(ABS(L{r})>=0.1,"Sí","No"))', c["sustancial"] or None),
            fx(f'IF(M{r}="","{_CONCL_BLOQ}",IF(M{r}="Sí","{_CONCL_SUST}","{_CONCL_NO}"))', c["conclusion"]),
            ("NIIF para las PYMES: la Sección 11 (11.37) exige condiciones «sustancialmente diferentes» sin umbral cuantitativo; esta prueba del "
             "10 % no existe en PYMES y se aplica por analogía con la NIIF 9 B3.3.6 (jerarquía 10.6), como juicio del auditor."
             if pymes else "NIIF 9 3.3.2 y B3.3.6: prueba del 10 % sobre el valor presente descontado a la tasa de interés efectiva original."),
        ])

    t = d["totales"]
    tot = FILA0 + N
    fila_res = {k: FILA0 + i for i, k in enumerate(res["labels"])}
    CC = ref("13_Conciliacion")
    ref_res = {"pasivoRegistrado": f"{CC}E{tot}", "pasivo": f"{CC}B{tot}", "ajuste": f"B{fila_res['pasivo']}-B{fila_res['pasivoRegistrado']}",
               "capitalContractual": f"SUM({CA}E{FILA0}:E{fin})", "interesesDevengados": f"SUM({CA}F{FILA0}:F{fin})",
               "interesesRegistrados": f"{CC}D{tot}", "corriente": f"{CC}G{tot}", "noCorriente": f"{CC}H{tot}",
               "reclasificacionCovenant": f"SUM({CL}G{FILA0}:G{fin})-SUM({CL}E{FILA0}:E{fin})",
               "gastoFinanciero": f"{CC}I{tot}", "diferenciaGasto": f"SUM({IN}G{FILA0}:G{fin})", "comisionesPorAmortizar": f"SUM({CM}G{FILA0}:G{fin})"}
    resumen = [[res["labels"][k], fx(ref_res[k], t[k])] for k in res["labels"]]

    n_ = "n"
    S = lambda col, v: suma(col, fin, v)
    fin_t = FILA0 + len(tab) - 1

    # Explicaciones humanas de «Cómo se calcula esta hoja» (una por columna calculada).
    ex01 = {"Importe": ("Trae cada importe de la cédula donde se calcula, concepto por concepto: los saldos auditados, registrados, el "
                        "ajuste, la clasificación y el gasto salen de los totales de la hoja 13 (Conciliación y ajuste); el capital y el "
                        "interés devengado, de la hoja 06 (Costo amortizado); la diferencia de gasto, de la hoja 08; los costos por "
                        "amortizar, de la hoja 07; la reclasificación por covenants, de la hoja 11. El ajuste es el pasivo recalculado "
                        "menos el registrado de este mismo resumen.")}
    ex04 = {
        "Sistema": "Copia el sistema de amortización del préstamo (francés, alemán o bullet) tal como quedó en la hoja 03 (Universo de préstamos).",
        "Monto": "Copia el monto desembolsado por el banco para esta operación desde la hoja 03 (Universo de préstamos).",
        "Comisiones y costos": ("Trae las comisiones y costos de transacción pagados al obtener el préstamo desde la hoja 03 (Universo de "
                                "préstamos); si el cliente no los informó, se toman como cero."),
        "Importe neto recibido (5.1.1 / 11.13)": ("Resta al monto desembolsado las comisiones y costos de transacción: es el dinero que "
                                                  "realmente recibió la entidad y el punto de partida del costo amortizado."),
        "Plazo (meses)": "Copia el plazo total del préstamo, en meses, informado en la hoja 03 (Universo de préstamos).",
        "Meses por período": ("Convierte la periodicidad de pago de la hoja 03 en meses: mensual = 1, trimestral = 3, semestral = 6 y "
                              "cualquier otra (anual) = 12."),
        "Períodos": "Divide el plazo en meses para los meses de cada período: es el número de cuotas que tiene el préstamo.",
        "Tasa nominal anual (%)": "Copia la tasa de interés nominal anual pactada en el contrato, tal como figura en la hoja 03 (Universo de préstamos).",
        "Tasa periódica nominal": ("Pasa la tasa nominal anual a la tasa de cada período: la divide para 100 y la multiplica por los meses "
                                   "del período sobre 12."),
        "Cuota fija (francés)": ("Solo para el sistema francés: calcula con la función PAGO la cuota constante que amortiza el monto en el "
                                 "número de períodos a la tasa periódica nominal. En alemán o bullet queda en blanco."),
        "TIE periódica (TIR de los flujos)": ("Calcula la TIR de los flujos de esta operación en la hoja 05 (Tabla de amortización): el "
                                              "importe neto recibido en negativo y luego cada pago. Es la tasa que iguala los pagos con "
                                              "lo recibido, e incluye el efecto de las comisiones."),
        "TIE anual efectiva": "Convierte la TIE periódica a tasa anual compuesta: (1 + TIE periódica) elevado al número de períodos del año, menos 1.",
        "Tasa efectiva anual contractual": ("Convierte la tasa periódica nominal del contrato a tasa anual compuesta, sin comisiones, para "
                                            "compararla con la TIE anual."),
        "Efecto de las comisiones en la tasa": ("Resta la tasa efectiva anual contractual de la TIE anual efectiva: muestra cuántos puntos "
                                                "de tasa suman las comisiones y costos de transacción."),
    }
    ex05 = {
        "Pago contractual": ("Pago de cada período según el sistema de la hoja 04: en francés, la cuota fija; en alemán, el monto dividido "
                             "para los períodos más el interés nominal; en bullet, solo el interés y, en el último período, el interés más "
                             "todo el capital."),
        "Capital inicial": "Toma el capital final de la fila anterior de esta misma tabla: es lo que se debe al empezar el período.",
        "Interés nominal": "Multiplica el capital inicial del período por la tasa periódica nominal de la hoja 04 (Condiciones y TIE).",
        "Capital amortizado": "Resta al pago contractual el interés nominal: es la parte del pago que reduce la deuda de capital.",
        "Capital final": ("En el período 0 es el monto desembolsado (hoja 04); en los demás, el capital inicial menos el capital amortizado "
                          "en el período."),
        "Flujo para la TIE": ("En el período 0 es el importe neto recibido con signo negativo (hoja 04); en los demás, el pago contractual. "
                              "Con esta columna se calcula la TIR que da la TIE."),
        "Costo amortizado inicial": "Toma el costo amortizado final de la fila anterior de esta misma tabla.",
        "Interés a la TIE (Apéndice A)": ("Multiplica el costo amortizado inicial del período por la TIE periódica de la hoja 04: es el "
                                          "gasto financiero que corresponde reconocer en el período."),
        "Amortización (pago − interés)": "Resta al pago contractual el interés a la TIE: es lo que el pago reduce el costo amortizado.",
        "Costo amortizado final": ("En el período 0 es el importe neto recibido (hoja 04); en los demás, el costo amortizado inicial menos "
                                   "la amortización del período."),
    }
    ex06 = {
        "Meses al corte": "Cuenta los meses completos transcurridos entre la fecha de desembolso (hoja 03) y la fecha de corte (hoja 02).",
        "Períodos vencidos al corte": ("Divide los meses al corte para los meses de cada período (hoja 04) y toma la parte entera, sin "
                                       "pasar del número total de períodos: son las cuotas ya vencidas al corte."),
        "Fracción del período en curso": ("Mide qué parte del período en curso ya pasó al corte: días desde el último vencimiento hasta el "
                                          "corte divididos para los días del período. Si el préstamo ya venció por completo, es cero."),
        "Capital contractual al corte": ("Busca en la hoja 05 (Tabla de amortización) el capital final de esta operación en el último "
                                         "período vencido al corte."),
        "Interés nominal devengado": ("Multiplica el capital contractual al corte por la tasa periódica nominal (hoja 04) y por la fracción "
                                      "del período en curso: es el interés del contrato devengado y aún no vencido."),
        "Costo amortizado al último vencimiento": ("Busca en la hoja 05 (Tabla de amortización) el costo amortizado final de esta "
                                                   "operación en el último período vencido al corte."),
        "Interés a la TIE devengado": ("Multiplica el costo amortizado al último vencimiento por la TIE periódica (hoja 04) y por la "
                                       "fracción del período en curso ya transcurrida."),
        "Costo amortizado al corte": "Suma el costo amortizado al último vencimiento y el interés a la TIE devengado hasta el corte: es el pasivo auditado.",
        "Meses al inicio del ejercicio": ("Cuenta los meses completos entre el desembolso y el inicio del ejercicio (hoja 02); si el "
                                          "préstamo se desembolsó después del inicio, marca −1 (préstamo nuevo del año)."),
        "Períodos vencidos al inicio": ("Cuotas ya vencidas al inicio del ejercicio: meses al inicio divididos para los meses del período, "
                                        "parte entera y sin pasar del total. En un préstamo nuevo del año es cero."),
        "Fracción al inicio": ("Parte del período que estaba en curso al inicio del ejercicio y que ya había transcurrido; es cero si el "
                               "préstamo es nuevo del año o ya había vencido por completo."),
        "Capital contractual al inicio": ("Busca en la hoja 05 el capital final de esta operación en el último período vencido al inicio "
                                          "del ejercicio; cero si el préstamo es nuevo del año."),
        "Interés nominal devengado al inicio": ("Multiplica el capital contractual al inicio por la tasa periódica nominal (hoja 04) y por "
                                                "la fracción al inicio: interés del contrato devengado al empezar el ejercicio."),
        "Costo amortizado al vencimiento previo al inicio": ("Busca en la hoja 05 el costo amortizado final de esta operación en el último "
                                                             "período vencido al inicio del ejercicio; cero si el préstamo es nuevo del año."),
        "Interés a la TIE devengado al inicio": ("Multiplica el costo amortizado al vencimiento previo al inicio por la TIE periódica "
                                                 "(hoja 04) y por la fracción al inicio."),
        "Costo amortizado al inicio": "Suma el costo amortizado al vencimiento previo al inicio y el interés a la TIE devengado a esa fecha: es el saldo de apertura.",
        "Desembolso neto del ejercicio": ("Si el préstamo se desembolsó dentro del ejercicio, trae el importe neto recibido de la hoja 04; "
                                          "si ya existía al inicio, es cero."),
        "Pagos del ejercicio": ("Suma en la hoja 05 los pagos contractuales de esta operación de los períodos que vencieron dentro del "
                                "ejercicio (después del último vencido al inicio y hasta el último vencido al corte)."),
        "Interés nominal del ejercicio": ("Suma el interés nominal de los períodos vencidos en el ejercicio (hoja 05), más el devengado al "
                                          "corte y menos el que ya estaba devengado al inicio."),
        "Gasto financiero a la TIE del ejercicio": ("Suma el interés a la TIE de los períodos vencidos en el ejercicio (hoja 05), más el "
                                                    "devengado a la TIE al corte y menos el devengado al inicio: es el gasto financiero que "
                                                    "corresponde al año."),
        "Comprobación del movimiento (0)": ("Cuadra el movimiento del año: costo amortizado al inicio + desembolso + gasto a la TIE − pagos "
                                            "− costo amortizado al corte. Debe dar cero; otro valor indica un error en la tabla."),
    }
    ex07 = {
        "Comisiones y costos": "Trae las comisiones y costos de transacción de la operación desde la hoja 04 (Condiciones y TIE).",
        "Tratamiento del cliente": ("Usa el tratamiento que informó el cliente en la hoja 03; si no lo informó: sin comisiones, «Sin "
                                    "comisiones»; si el capital registrado es igual al capital contractual al corte (hoja 06), «Gasto "
                                    "(inferido)»; en otro caso, «TIE»."),
        "Interés nominal del ejercicio": "Trae el interés nominal del ejercicio de esta operación desde la hoja 06 (Costo amortizado).",
        "Gasto a la TIE del ejercicio": "Trae el gasto financiero a la TIE del ejercicio de esta operación desde la hoja 06 (Costo amortizado).",
        "Amortización de costos del ejercicio": ("Resta el interés nominal del gasto a la TIE: es la parte de las comisiones que se lleva a "
                                                 "resultados en este ejercicio."),
        "Costo por amortizar al corte": ("Resta al capital contractual al corte el costo amortizado al último vencimiento (ambos de la "
                                         "hoja 06): son las comisiones que aún quedan por llevar a gasto."),
        "Llevado a gasto indebidamente (por amortizar)": ("Si el tratamiento del cliente empieza por «Gasto», toma el costo por amortizar "
                                                          "al corte: es lo que el cliente ya llevó a resultados antes de tiempo. En otro "
                                                          "caso, cero."),
    }
    ex08 = {
        "Tasa nominal anual (%)": "Trae la tasa nominal anual del contrato desde la hoja 04 (Condiciones y tasa de interés efectiva).",
        "TIE anual efectiva": "Trae la TIE anual efectiva de la operación, calculada en la hoja 04 (Condiciones y tasa de interés efectiva).",
        "Interés nominal del ejercicio": "Trae de la hoja 06 (Costo amortizado) el interés del ejercicio calculado a la tasa del contrato.",
        "Gasto financiero a la TIE": "Trae de la hoja 06 (Costo amortizado) el gasto financiero del ejercicio calculado a la TIE.",
        "Gasto financiero registrado": "Copia el gasto financiero del año que registró el cliente (hoja 03); si no lo informó, queda en blanco.",
        "Diferencia de gasto": ("Resta el gasto registrado del gasto a la TIE recalculado; solo se calcula si el cliente informó su gasto. "
                                "Positivo: el cliente registró menos gasto."),
        "Interés contractual devengado al corte": "Trae de la hoja 06 el interés nominal devengado desde el último vencimiento hasta el corte.",
        "Intereses por pagar registrados": "Copia los intereses por pagar que registró el cliente (hoja 03); si no los informó, cuenta cero.",
        "Interés devengado no registrado": ("Resta los intereses por pagar registrados del interés contractual devengado al corte: es el "
                                            "interés que falta provisionar."),
    }
    ex09 = {
        "Capital según tabla": "Trae el capital contractual al corte de esta operación calculado en la hoja 06 (Costo amortizado).",
        "Saldo confirmado por el banco": "Copia el saldo de capital que confirmó el banco (hoja 03); si no hay confirmación, queda en blanco.",
        "Capital registrado": "Copia el saldo de capital registrado por el cliente (hoja 03); si no lo informó, cuenta cero.",
        "Costos por amortizar (cliente a la TIE)": ("Si el cliente aplica la TIE a las comisiones (hoja 07), trae el costo por amortizar "
                                                    "al corte, porque su saldo contable está neto de esas comisiones; si no, cero."),
        "Diferencia no explicada": ("Resta al saldo confirmado el capital registrado y los costos por amortizar: lo que queda no tiene "
                                    "explicación. Solo se calcula si hay saldo confirmado."),
        "Confirmado − tabla": "Resta al saldo confirmado por el banco el capital según la tabla recalculada; en blanco si no hay confirmación.",
        "Pagos del ejercicio (tabla)": "Trae de la hoja 06 los pagos contractuales que vencieron en el ejercicio según la tabla de amortización.",
        "Pagos informados": "Copia los pagos del año (capital más interés) que informó el cliente en la hoja 03; en blanco si no los informó.",
        "Diferencia de pagos": "Resta los pagos informados de los pagos según la tabla; solo se calcula si el cliente informó sus pagos.",
    }
    ex10 = {
        "Covenant": "Copia el ratio pactado como covenant (deuda/activos, deuda/EBITDA, DSCR…) de la hoja 03; en blanco si no hay covenant.",
        "Ratio de la entidad": ("Busca el covenant de esta operación en la hoja 12 (Endeudamiento) y trae el ratio calculado para la "
                                "entidad; en blanco si no hay covenant."),
        "Límite": "Busca el covenant en la hoja 12 (Endeudamiento) y trae el límite pactado en el contrato, tomado de los parámetros.",
        "Tipo de límite": "Busca el covenant en la hoja 12 (Endeudamiento) y trae si el límite es un máximo o un mínimo.",
        "Cumple el límite": ("Busca el covenant en la hoja 12 (Endeudamiento) y trae si la entidad cumple el límite; queda en blanco si "
                             "falta el ratio, el límite o, en el DSCR, la definición contractual."),
        "Incumplimiento declarado": "Copia si el cliente declaró incumplimiento del covenant (hoja 03); si no dijo nada, se toma como «No».",
        "Incumplimiento al corte": "Marca «Sí» si el cliente declaró el incumplimiento o si el recálculo muestra que no cumple el límite.",
        "Dispensa válida al corte (NIC 1 75)": ("«Sí» cuando hay fecha de dispensa, es anterior o igual al corte y la gracia no tiene fecha "
                                                "o llega al menos 12 meses después del corte (hojas 02 y 03)."),
        "Deuda exigible: toda corriente (74)": ("«Sí» cuando hay incumplimiento al corte, no hay dispensa válida y el covenant no se mide "
                                                "después del corte: entonces toda la deuda pasa a corriente."),
        "Se mide después del corte (72B)": ("«Sí» si la fecha de medición del covenant informada en la hoja 03 es posterior al corte: ese "
                                            "covenant no reclasifica la deuda, solo se revela."),
        "Definición aplicada del covenant": ("Busca el covenant en la hoja 12 (Endeudamiento) y trae la definición con la que se midió "
                                             "(la del contrato o, en el DSCR sin definición, la analítica de la firma)."),
    }
    ex11 = {
        "Costo amortizado al corte": "Trae el costo amortizado al corte de esta operación calculado en la hoja 06 (Costo amortizado).",
        "Período a 12 meses": ("Suma a los períodos vencidos al corte (hoja 06) los períodos que caben en 12 meses, sin pasar del total "
                               "de períodos: es la cuota que vence un año después del corte."),
        "Capital contractual después de 12 meses": ("Busca en la hoja 05 (Tabla de amortización) el capital final de esta operación en el "
                                                    "período a 12 meses: es lo que se seguirá debiendo dentro de un año."),
        "Corriente: capital de 12 meses + interés devengado (69 c)": ("Capital contractual al corte (hoja 06) menos el que queda después "
                                                                      "de 12 meses, más el interés a la TIE devengado; sin superar el "
                                                                      "costo amortizado al corte."),
        "Exigible por covenant": "Trae de la hoja 10 (Covenants) si la deuda es exigible por un covenant incumplido sin dispensa válida.",
        "Corriente auditado": ("Si la deuda es exigible por covenant, todo el costo amortizado es corriente; si no, la porción que vence "
                               "en 12 meses más el interés devengado."),
        "No corriente auditado": "Resta el corriente auditado del costo amortizado al corte: es la parte que vence después de 12 meses.",
        "Corriente registrado": "Copia la porción corriente que presentó el cliente (hoja 03); en blanco si no la informó.",
        "Diferencia corriente": ("Resta el corriente registrado del corriente auditado; solo se calcula si el cliente informó su porción "
                                 "corriente. Positivo: falta reclasificar a corriente."),
    }
    ex12 = {
        "Numerador": ("Cambia por fila: la deuda auditada es la suma del costo amortizado al corte (hoja 06), el gasto financiero la suma "
                      "del gasto a la TIE y el servicio de la deuda la suma de los pagos del ejercicio; en los ratios, la deuda auditada, "
                      "el EBITDA o EBIT según la base elegida, o el efectivo para el servicio de la deuda (hoja 02)."),
        "Denominador": ("En cada ratio trae la base de la hoja 02 (Parámetros): total de activos, patrimonio o EBITDA; en la cobertura, "
                        "el gasto financiero del ejercicio; en el DSCR, el servicio de la deuda del contrato o, si falta, el del ejercicio."),
        "Ratio (veces)": "Divide el numerador para el denominador; queda en blanco si falta alguno o si el denominador es cero o negativo.",
        "Límite (veces)": "Trae el límite pactado para este ratio desde la hoja 02 (Parámetros); en blanco si el contrato no lo fija.",
        "Cumple (solo con definición contractual)": ("Compara el ratio con el límite: si es un máximo, cumple cuando no lo supera; si es un "
                                                     "mínimo, cuando lo alcanza. En el DSCR solo concluye si hay definición contractual."),
        "Definición aplicada": ("En el DSCR muestra la definición contractual de la hoja 02 o, si falta, «DSCR analítico de la firma», que "
                                "no concluye incumplimiento."),
    }
    ex13 = {
        "Costo amortizado auditado": "Trae el costo amortizado al corte de esta operación, calculado en la hoja 06 (Costo amortizado).",
        "Capital registrado": "Copia el saldo de capital que registró el cliente en la hoja 03 (Universo de préstamos); vacío cuenta cero.",
        "Intereses registrados": "Copia los intereses por pagar que registró el cliente en la hoja 03 (Universo de préstamos); vacío cuenta cero.",
        "Total registrado": "Suma el capital registrado y los intereses registrados: es el pasivo según los libros del cliente.",
        "Ajuste propuesto": "Resta el total registrado del costo amortizado auditado. Positivo: el pasivo del cliente está subestimado.",
        "Corriente auditado": "Trae la porción corriente auditada de la operación desde la hoja 11 (Clasificación corriente / no corriente).",
        "No corriente auditado": "Trae la porción no corriente auditada de la operación desde la hoja 11 (Clasificación corriente / no corriente).",
        "Gasto financiero (TIE)": "Trae el gasto financiero del ejercicio a la TIE de esta operación desde la hoja 06 (Costo amortizado).",
    }
    ex14 = {
        "Años al descuento (días ÷ 365)": ("Cuenta los días entre la fecha de la modificación (hoja 03) y la fecha del flujo y los divide "
                                           "para 365; en blanco si no hay fecha de modificación."),
        "TIE anual original": "Trae la TIE anual efectiva original del préstamo desde la hoja 04 (Condiciones y tasa de interés efectiva).",
        "Valor presente a la TIE original": ("Descuenta el importe del flujo a la TIE anual original por los años al descuento: importe ÷ "
                                             "(1 + TIE) elevado a los años. En blanco si no hay años."),
    }
    ex15 = {
        "Modificación declarada": "Copia si el cliente declaró una modificación de condiciones en el año (hoja 03); si no dijo nada, «No».",
        "TIE anual original": "Trae la TIE anual efectiva original de la operación desde la hoja 04 (Condiciones y TIE).",
        "Flujos originales restantes informados": "Cuenta cuántos flujos «Original» de esta operación hay en la hoja 14 (Flujos de la modificación).",
        "Flujos modificados informados": "Cuenta cuántos flujos «Modificado» de esta operación hay en la hoja 14 (Flujos de la modificación).",
        "Valor presente de los flujos originales restantes": ("Suma en la hoja 14 el valor presente a la TIE original de los flujos "
                                                              "«Original» de esta operación."),
        "Valor presente de los flujos modificados": "Suma en la hoja 14 el valor presente a la TIE original de los flujos «Modificado» de esta operación.",
        "Comisiones netas pagadas por la modificación": ("Copia las comisiones pagadas al prestamista netas de las recibidas por la "
                                                         "adenda (hoja 03); vacío cuenta cero."),
        "Valor presente de las nuevas condiciones": ("Suma el valor presente de los flujos modificados y las comisiones netas. Queda en "
                                                     "blanco si faltan flujos originales o modificados, la fecha de modificación o el "
                                                     "valor presente original."),
        "Diferencia": "Resta el valor presente de los flujos originales restantes del valor presente de las nuevas condiciones.",
        "Diferencia / valor presente original": "Divide la diferencia para el valor presente de los flujos originales restantes: es el porcentaje de cambio.",
        "¿Condiciones sustancialmente diferentes (≥ 10 %)?": ("«Sí» si la diferencia, en valor absoluto, llega al 10 % del valor presente "
                                                              "original; en blanco si la prueba no se pudo calcular."),
        "Conclusión": ("Redacta la conclusión: sin resultado, «Dato insuficiente: conclusión bloqueada»; si es sustancial, baja del pasivo "
                       "original y alta de uno nuevo; si no, el pasivo continúa y los costos se amortizan."),
    }

    return [
        hoja("01_Resumen", "Resumen", [["Concepto", "t"], ["Importe", "n"]], resumen, explica=ex01),
        hoja("02_Parametros", "Parámetros", [["Parámetro", "t"], ["Valor", "x"], ["Sustento", "t"]], parametros),
        hoja("03_Prestamos", "Universo de préstamos", cols03, universo),
        hoja("04_Condiciones_TIE", "Condiciones y tasa de interés efectiva",
             [["Operación", "t"], ["Sistema", "t"], ["Monto", n_], ["Comisiones y costos", n_], ["Importe neto recibido (5.1.1 / 11.13)", n_],
              ["Plazo (meses)", "i"], ["Meses por período", "i"], ["Períodos", "i"], ["Tasa nominal anual (%)", "x"], ["Tasa periódica nominal", "p"],
              ["Cuota fija (francés)", n_], ["TIE periódica (TIR de los flujos)", "p"], ["TIE anual efectiva", "p"],
              ["Tasa efectiva anual contractual", "p"], ["Efecto de las comisiones en la tasa", "p"]], cond,
             ["TOTAL", "", S("C", sum(c["monto"] for c in cs)), S("D", sum(c["com"] for c in cs)), S("E", sum(c["neto"] for c in cs)),
              None, None, None, None, None, None, None, None, None, None], explica=ex04),
        hoja("05_Tabla_amortizacion", "Tabla de amortización",
             [["Operación", "t"], ["Período", "i"], ["Vencimiento", "d"], ["Pago contractual", n_], ["Capital inicial", n_], ["Interés nominal", n_],
              ["Capital amortizado", n_], ["Capital final", n_], ["Flujo para la TIE", n_], ["Costo amortizado inicial", n_],
              ["Interés a la TIE (Apéndice A)", n_], ["Amortización (pago − interés)", n_], ["Costo amortizado final", n_]], tabla,
             ["TOTAL", None, None, suma("D", fin_t, sum(x["pago"] or 0 for x in tab)), None, suma("F", fin_t, sum(x["int_nom"] or 0 for x in tab)),
              suma("G", fin_t, sum(x["cap"] or 0 for x in tab)), None, None, None, suma("K", fin_t, sum(x["int_tie"] or 0 for x in tab)),
              suma("L", fin_t, sum(x["amort"] or 0 for x in tab)), None], explica=ex05),
        hoja("06_Costo_amortizado", "Costo amortizado al corte y del ejercicio",
             [["Operación", "t"], ["Meses al corte", "i"], ["Períodos vencidos al corte", "i"], ["Fracción del período en curso", "p"],
              ["Capital contractual al corte", n_], ["Interés nominal devengado", n_], ["Costo amortizado al último vencimiento", n_],
              ["Interés a la TIE devengado", n_], ["Costo amortizado al corte", n_], ["Meses al inicio del ejercicio", "i"],
              ["Períodos vencidos al inicio", "i"], ["Fracción al inicio", "p"], ["Capital contractual al inicio", n_],
              ["Interés nominal devengado al inicio", n_], ["Costo amortizado al vencimiento previo al inicio", n_],
              ["Interés a la TIE devengado al inicio", n_], ["Costo amortizado al inicio", n_], ["Desembolso neto del ejercicio", n_],
              ["Pagos del ejercicio", n_], ["Interés nominal del ejercicio", n_], ["Gasto financiero a la TIE del ejercicio", n_],
              ["Comprobación del movimiento (0)", n_]], cam,
             ["TOTAL", None, None, None, S("E", t["capitalContractual"]), S("F", t["interesesDevengados"]), None, None, S("I", t["pasivo"]),
              None, None, None, None, None, None, None, S("Q", sum(c["ca_tot_i"] for c in cs)), S("R", sum(c["alta"] for c in cs)),
              S("S", d["servicio"]), S("T", sum(c["int_anio"] for c in cs)), S("U", t["gastoFinanciero"]), None], explica=ex06),
        hoja("07_Comisiones", "Comisiones y costos de transacción",
             [["Operación", "t"], ["Comisiones y costos", n_], ["Tratamiento del cliente", "t"], ["Interés nominal del ejercicio", n_],
              ["Gasto a la TIE del ejercicio", n_], ["Amortización de costos del ejercicio", n_], ["Costo por amortizar al corte", n_],
              ["Llevado a gasto indebidamente (por amortizar)", n_]], com,
             ["TOTAL", S("B", sum(c["com"] for c in cs)), "", None, None, S("F", sum(c["amort_costos"] for c in cs)),
              S("G", t["comisionesPorAmortizar"]), S("H", sum(c["efecto_gasto"] for c in cs))], explica=ex07),
        hoja("08_Intereses", "Recálculo de intereses",
             [["Operación", "t"], ["Tasa nominal anual (%)", "x"], ["TIE anual efectiva", "p"], ["Interés nominal del ejercicio", n_],
              ["Gasto financiero a la TIE", n_], ["Gasto financiero registrado", n_], ["Diferencia de gasto", n_],
              ["Interés contractual devengado al corte", n_], ["Intereses por pagar registrados", n_], ["Interés devengado no registrado", n_]], inte,
             ["TOTAL", None, None, S("D", sum(c["int_anio"] for c in cs)), S("E", t["gastoFinanciero"]), None, S("G", t["diferenciaGasto"]),
              S("H", t["interesesDevengados"]), S("I", t["interesesRegistrados"]), S("J", t["interesesDevengados"] - t["interesesRegistrados"])],
             explica=ex08),
        hoja("09_Confirmacion", "Confirmación bancaria y pagos",
             [["Operación", "t"], ["Banco", "t"], ["Capital según tabla", n_], ["Saldo confirmado por el banco", n_], ["Capital registrado", n_],
              ["Costos por amortizar (cliente a la TIE)", n_], ["Diferencia no explicada", n_], ["Confirmado − tabla", n_],
              ["Pagos del ejercicio (tabla)", n_], ["Pagos informados", n_], ["Diferencia de pagos", n_]], conf,
             ["TOTAL", "", S("C", t["capitalContractual"]), None, S("E", sum(c["saldo_reg"] for c in cs)), S("F", sum(c["explicado"] for c in cs)),
              None, None, S("I", d["servicio"]), None, None], explica=ex09),
        hoja("10_Covenants", "Covenants y dispensas",
             [["Operación", "t"], ["Covenant", "t"], ["Ratio de la entidad", "x"], ["Límite", "x"], ["Tipo de límite", "t"], ["Cumple el límite", "t"],
              ["Incumplimiento declarado", "t"], ["Incumplimiento al corte", "t"], ["Fecha de la dispensa", "d"], ["Gracia hasta", "d"],
              ["Dispensa válida al corte (NIC 1 75)", "t"], ["Deuda exigible: toda corriente (74)", "t"],
              ["Fecha de medición del covenant", "d"], ["Se mide después del corte (72B)", "t"],
              ["Definición aplicada del covenant", "t"]], cov, explica=ex10),
        hoja("11_Clasificacion", "Clasificación corriente / no corriente",
             [["Operación", "t"], ["Costo amortizado al corte", n_], ["Período a 12 meses", "i"], ["Capital contractual después de 12 meses", n_],
              ["Corriente: capital de 12 meses + interés devengado (69 c)", n_], ["Exigible por covenant", "t"], ["Corriente auditado", n_], ["No corriente auditado", n_],
              ["Corriente registrado", n_], ["Diferencia corriente", n_]], cla,
             ["TOTAL", S("B", t["pasivo"]), None, None, S("E", sum(c["cp_venc"] for c in cs)), "", S("G", t["corriente"]),
              S("H", t["noCorriente"]), None, None], explica=ex11),
        hoja("12_Endeudamiento", "Endeudamiento y ratios de covenants (analítica, no requisito NIIF)",
             [["Concepto", "t"], ["Numerador", n_], ["Denominador", n_], ["Ratio (veces)", "x"], ["Límite (veces)", "x"], ["Tipo", "t"],
              ["Cumple (solo con definición contractual)", "t"], ["Definición aplicada", "t"]], endeu, explica=ex12),
        hoja("13_Conciliacion", "Conciliación y ajuste",
             [["Operación", "t"], ["Costo amortizado auditado", n_], ["Capital registrado", n_], ["Intereses registrados", n_], ["Total registrado", n_],
              ["Ajuste propuesto", n_], ["Corriente auditado", n_], ["No corriente auditado", n_], ["Gasto financiero (TIE)", n_]], conc,
             ["TOTAL", S("B", t["pasivo"]), S("C", sum(c["saldo_reg"] for c in cs)), S("D", t["interesesRegistrados"]), S("E", t["pasivoRegistrado"]),
              S("F", t["ajuste"]), S("G", t["corriente"]), S("H", t["noCorriente"]), S("I", t["gastoFinanciero"])], explica=ex13),
        hoja("14_Flujos_modificacion", "Flujos de la modificación (adenda) descontados a la TIE original",
             [["Operación", "t"], ["Escenario", "t"], ["Fecha del flujo", "d"], ["Importe del flujo", n_], ["Años al descuento (días ÷ 365)", "x"],
              ["TIE anual original", "p"], ["Valor presente a la TIE original", n_]], flujos, explica=ex14),
        hoja("15_Prueba_10pct", "Prueba del 10 % (NIIF 9 3.3.2 y B3.3.6)",
             [["Operación", "t"], ["Modificación declarada", "t"], ["Fecha de la modificación", "d"], ["TIE anual original", "p"],
              ["Flujos originales restantes informados", "i"], ["Flujos modificados informados", "i"],
              ["Valor presente de los flujos originales restantes", n_], ["Valor presente de los flujos modificados", n_],
              ["Comisiones netas pagadas por la modificación", n_], ["Valor presente de las nuevas condiciones", n_], ["Diferencia", n_],
              ["Diferencia / valor presente original", "p"], ["¿Condiciones sustancialmente diferentes (≥ 10 %)?", "t"], ["Conclusión", "t"],
              ["Marco aplicado", "t"]], prueba, explica=ex15),
        hoja("16_Problemas", "Problemas encontrados", [["Código", "t"], ["Descripción", "t"], ["Importe", "n"]],
             [[e["code"], e["message"], float(e["amount"])] for e in res["exceptions"]]),
    ]


# --- definición ------------------------------------------------------------------------

def definicion() -> dict:
    contenido = ("Una fila por operación: código, banco, fecha de desembolso, monto, plazo en meses, tasa nominal anual, periodicidad, "
                 "sistema (francés, alemán o bullet), comisiones y costos de transacción y su tratamiento, pagos del año, saldo confirmado "
                 "por el banco, saldo de capital registrado, intereses por pagar, gasto financiero del año, porción corriente registrada, "
                 "covenant, incumplimiento, fecha de la dispensa, fin de la gracia, la fecha de medición del covenant según el contrato y, si hubo "
                 "adenda, la modificación de condiciones (sí/no), su fecha y las comisiones pagadas al prestamista netas de las recibidas. Sin filas de total.")
    flujos = ("Anexo opcional, solo para los préstamos con adenda: una fila por flujo con la operación, el escenario («Original» para los flujos "
              "contractuales que restaban a la fecha de la modificación y «Modificado» para los de la adenda), la fecha y el importe del pago. "
              "Sin los dos escenarios completos la prueba del 10 % no concluye.")
    return {
        "name": "Préstamos y obligaciones financieras",
        "area": "Préstamos y obligaciones financieras",
        "processor": "prestamos_obligaciones",
        "frameworks": ["NIIF completas", "NIIF para las PYMES"],
        "summary": ("Recalcula por préstamo la tabla de amortización, la tasa de interés efectiva con comisiones y costos de transacción, "
                    "el costo amortizado con intereses devengados, el gasto financiero del ejercicio, la confirmación bancaria, los covenants "
                    "y dispensas, la clasificación corriente / no corriente y los ratios de endeudamiento (NIIF 9, NIC 1 69–76 / Secciones 11 y 4)."),
        "source": {"organization": "IFRS Foundation / Unión Europea", "type": "Norma contable", "date": "",
                   "document": ("NIIF 9 Instrumentos financieros (Reglamento (UE) 2016/2067 y consolidado 2023/1803): 3.3.2 (modificación sustancial), "
                                "4.2.1 (pasivos a costo amortizado), 5.1.1 (medición inicial con costos de transacción), 5.3.1 (costo amortizado; método del interés efectivo en el Apéndice A), "
                                "Apéndice A (tasa de interés efectiva, costo amortizado, costos de transacción); B3.3.6 (prueba del 10 %) y B5.4.1–B5.4.3 (en especial B5.4.2 c): comisiones de originación en la TIE). "
                                "NIIF 7 párr. 7, 18–19 y 39. NIC 1 párr. 69–76 y 76ZA con las modificaciones del Reglamento (UE) 2023/2822, "
                                "vigentes para ejercicios desde el 1-1-2024 (139U y 139W). NIIF 18 para ejercicios desde el 1-1-2027 (NIIF 18 párr. 101 y B99–B106; covenants "
                                "en B100, B102–B103, B105–B106)."),
                   "url": "https://eur-lex.europa.eu/legal-content/ES/TXT/HTML/?uri=CELEX:32023R2822"},
        "source_pymes": {"organization": "IFRS Foundation", "type": "Norma contable", "date": "",
                         "document": ("NIIF para las PYMES 2015: Sección 11, 11.13 (medición inicial, costos de transacción), 11.14 a) y 11.15–11.20 "
                                      "(costo amortizado y método del interés efectivo); Sección 4, 4.7 (pasivo corriente); Sección 32 (hechos "
                                      "posteriores); 11.47 (revelación de incumplimientos e infracciones de préstamos por pagar no subsanados al cierre). "
                                      "Edición 2025 (tercera): mismo modelo de costo amortizado (11.13/11.13B, 11.14 a), 11.15–11.20; 4.7 sin cambios); rige desde el 1-1-2027; aplicarla antes es "
                                      "adopción anticipada. Covenants: PYMES 4.7 d) (derecho incondicional); la NIC 1 72B/74/75 se usa por analogía (jerarquía 10.6), como juicio del auditor."),
                         "url": "https://www.ifrs.org/issued-standards/ifrs-for-smes/"},
        "nia": [
            {"document": "NIA 505", "section": "párr. 7 y 14", "requirement": "Confirmación externa de saldos, tasas, garantías y covenants con los bancos."},
            {"document": "NIA 500", "section": "párr. 9", "requirement": "Exactitud e integridad del anexo de préstamos contra el mayor y los contratos."},
            {"document": "NIA 540 (Revisada)", "section": "párr. 13, 18–30 (22–25: métodos, supuestos significativos y datos)", "requirement": "Método (TIE), datos (contratos) y supuestos del costo amortizado."},
            {"document": "NIA 560", "section": "párr. 6", "requirement": "Dispensas, refinanciaciones y pagos posteriores al cierre."},
            {"document": "NIA 570 (Revisada)", "section": "párr. 10–16", "requirement": "Incumplimientos de covenants y capacidad de pago como indicios de empresa en marcha. La NIA 570 (Revisada 2024) rige para períodos desde el 15-12-2026."},
        ],
        "calculo": [
            "Tasa periódica nominal = tasa nominal anual × meses del período ÷ 12 (cotéjela con el contrato).",
            "Pago: francés = PAGO(tasa; períodos; −monto); alemán = monto ÷ períodos + interés; bullet = interés y el capital en el último período.",
            "Importe neto recibido = monto − comisiones y costos de transacción (NIIF 9 5.1.1 / PYMES 11.13).",
            "TIE periódica = TIR de los flujos (−neto recibido, pagos contractuales) (Apéndice A: las comisiones integran la TIE).",
            "Tabla a la TIE: interés_t = saldo inicial_t × TIE; capital_t = pago_t − interés_t; saldo final_t = saldo inicial_t − capital_t (NIIF 9 4.2.1, 5.3.1 y Apéndice A / PYMES 11.15–11.20).",
            "Al corte: costo amortizado = saldo al último vencimiento + interés a la TIE devengado por días hasta el corte.",
            "Gasto financiero del ejercicio = interés a la TIE de los períodos vencidos en el año + devengo al corte − devengo al inicio.",
            "Comisiones llevadas a gasto: costo por amortizar = capital contractual − costo amortizado al último vencimiento.",
            "Corriente = capital contractual que vence en los 12 meses siguientes + interés devengado (tope: costo amortizado); si un covenant que debía cumplirse al cierre o antes "
            "(NIC 1 72B) se incumplió al corte sin dispensa obtenida hasta el corte con gracia ≥ 12 meses, todo es corriente (NIC 1 74–75 / PYMES 4.7 d)).",
            "Covenant cuya fecha de medición es posterior al corte: no reclasifica a corriente (NIC 1 72B); se exige la revelación del riesgo de que el pasivo pase a ser "
            "reembolsable dentro de los doce meses (NIC 1 76ZA). Si no se informa la fecha de medición, se mantiene el tratamiento anterior y se pide el dato.",
            "Incumplimientos no subsanados al cierre (principal, intereses u otras cláusulas): se exige revelar el detalle, el importe en libros y si se subsanó o renegoció antes de la "
            "autorización de los estados financieros (NIIF 7 18–19 / PYMES 11.47).",
            "Ratios (analítica): deuda / activos, deuda / patrimonio, deuda / EBITDA, cobertura = EBITDA o EBIT ÷ gasto financiero.",
            "DSCR: se calcula con la definición del contrato cuando el cliente la informa (parámetros «Definición contractual del DSCR» y, si el "
            "contrato lo define distinto, «Servicio de la deuda del DSCR según el contrato»). El contrato manda: no se impone ninguna definición "
            f"contable universal. Sin definición contractual la herramienta muestra el «{DSCR_ANALITICO}» = efectivo disponible ÷ servicio de la "
            "deuda del ejercicio según las tablas, que es solo un indicador para el auditor y NO concluye incumplimiento del covenant ni reclasifica deuda.",
            "Prueba del 10 % (NIIF 9 3.3.2 y B3.3.6), solo con el anexo de flujos: valor presente de las nuevas condiciones (flujos «Modificado» más "
            "las comisiones pagadas netas de las recibidas) frente al valor presente de los flujos originales que restaban, ambos descontados a la "
            "tasa de interés efectiva original. Si difiere al menos un 10 %, las condiciones son sustancialmente diferentes. Sin la fecha de la "
            "modificación, sin los flujos originales restantes o sin los de la adenda la prueba NO concluye: el resultado queda vacío y se emite "
            "«dato insuficiente: conclusión bloqueada». Nunca se presume «no sustancial».",
            "En la NIIF para las PYMES la Sección 11 (11.37) exige condiciones «sustancialmente diferentes» sin umbral cuantitativo: la prueba del "
            "10 % no existe en PYMES y el módulo la aplica por analogía con la NIIF 9 B3.3.6 (jerarquía 10.6), como juicio del auditor.",
            "Alcance: el módulo no remide el pasivo después de la modificación; las cédulas 04 a 13 siguen el contrato original.",
            "Nota (pendiente de decisión del socio): el contraste oficial observa que el devengo lineal por días aproxima el interés efectivo compuesto (simplificación).",
        ],
        "fields": _PRESTAMOS, "rules": [], "control": CONTROL, "primary": "ajuste",
        "campos": CAMPOS, "tipos": TIPOS, "parametros": dict(PARAMETROS), "etiquetas_parametros": ETIQUETAS_PARAM,
        "cedulas": [[n, lbl] for n, lbl in CEDULAS],
        "program": [
            {"code": "DEU-01", "objective": "Existencia e integridad de la deuda", "risk": "Préstamos no registrados o saldos distintos a los del banco",
             "assertion": "Existencia / Integridad", "procedure": "Confirmar con cada banco saldo, tasa, garantías y covenants; conciliar confirmado vs registrado y vs tabla",
             "evidence": "Confirmaciones bancarias, cédula 09", "criterion": "Diferencias explicadas", "source": "NIA 505 · NIIF 9 3.1.1"},
            {"code": "DEU-02", "objective": "Tabla de amortización e intereses", "risk": "Interés o capital mal calculados; interés devengado no registrado",
             "assertion": "Valoración / Corte", "procedure": "Rehacer la tabla contractual, recalcular el interés del ejercicio y el devengado al corte",
             "evidence": "Contratos, tablas del banco, cédulas 05, 06 y 08", "criterion": "Diferencias cuantificadas", "source": "NIIF 9 4.2.1, 5.3.1 y Apéndice A (método del interés efectivo) · PYMES 11.15–11.20"},
            {"code": "DEU-03", "objective": "Tasa de interés efectiva y comisiones", "risk": "Comisiones llevadas a gasto en lugar de integrarse a la TIE",
             "assertion": "Valoración", "procedure": "Calcular la TIE con los costos de transacción y comparar el costo amortizado con lo registrado",
             "evidence": "Liquidaciones de desembolso, cédulas 04 y 07", "criterion": "Costo amortizado a la TIE", "source": "NIIF 9 5.1.1 y Apéndice A · PYMES 11.13"},
            {"code": "DEU-04", "objective": "Covenants y dispensas",
             "risk": "Incumplimiento no revelado; deuda exigible presentada como no corriente; reclasificación por un covenant que se mide después del corte",
             "assertion": "Presentación",
             "procedure": "Recalcular los ratios pactados, verificar la fecha de medición de cada condición, los incumplimientos y la fecha y alcance de las dispensas",
             "evidence": "Contratos, cartas de dispensa, cédulas 10 y 12",
             "criterion": "NIC 1 72B (solo inciden las condiciones a cumplir al cierre o antes), 74–75 y 76ZA (revelación de las condiciones futuras)",
             "source": "NIC 1 69–76 y 76ZA · PYMES 4.7 (NIC 1 72B por analogía, 10.6)"},
            {"code": "DEU-08", "objective": "Revelación de impagos e incumplimientos",
             "risk": "Impagos de principal o intereses e infracciones de cláusulas no revelados", "assertion": "Presentación / Revelación",
             "procedure": "Identificar impagos e infracciones no subsanados al cierre y verificar su revelación en las notas",
             "evidence": "Contratos, estados de cuenta, cartas del banco, notas a los estados financieros",
             "criterion": "Detalle del incumplimiento, importe en libros y si se subsanó o renegoció antes de la autorización",
             "source": "NIIF 7 párr. 18–19 · PYMES 11.47 · NIA 560"},
            {"code": "DEU-05", "objective": "Clasificación corriente / no corriente", "risk": "Porción corriente mal clasificada",
             "assertion": "Presentación", "procedure": "Recalcular lo que vence en 12 meses y aplicar el efecto de los covenants", "evidence": "Cédula 11",
             "criterion": "NIC 1 69 c), 72B y 74", "source": "NIC 1 69–76 · PYMES 4.7"},
            {"code": "DEU-06", "objective": "Endeudamiento y capacidad de pago", "risk": "Endeudamiento sobre los límites; dudas de empresa en marcha",
             "assertion": "Presentación / Revelación",
             "procedure": "Analizar deuda/activos, deuda/patrimonio, deuda/EBITDA y cobertura (analítica, no requisito NIIF). Para el DSCR, obtener "
                          "del contrato su definición (numerador y denominador) y usarla; sin definición contractual el DSCR se presenta como "
                          f"«{DSCR_ANALITICO}», como indicador",
             "evidence": "Estados financieros, contratos de préstamo, cédula 12",
             "criterion": f"El contrato manda: el «{DSCR_ANALITICO}» no concluye incumplimiento del covenant",
             "source": "NIA 520 párr. 5–6 · NIA 570 · NIIF 7 18–19"},
            {"code": "DEU-07", "objective": "Modificaciones y refinanciaciones", "risk": "Refinanciación sustancial tratada como continuación",
             "assertion": "Valoración",
             "procedure": "Obtener la adenda con sus flujos, cargar en el anexo de flujos los contractuales originales restantes y los modificados "
                          "y resolver la prueba del 10 % descontando a la tasa de interés efectiva original",
             "evidence": "Adendas con su tabla de flujos, liquidaciones de comisiones, confirmaciones, cédulas 14 y 15",
             "criterion": "Sin flujos comparables la prueba no concluye: «dato insuficiente: conclusión bloqueada»; nunca se presume «no sustancial»",
             "source": "NIIF 9 3.3.2 y B3.3.6 · PYMES 11.37 (sin umbral; el 10 % por analogía, 10.6) · NIA 560"},
        ],
        "requests": [
            req("RQ-001", "Anexo de préstamos y obligaciones financieras al corte", "prestamos", "DEU-01", "Población a recalcular y conciliar con el mayor", content=contenido),
            req("RQ-002", "Anexo de flujos de la modificación (adenda): originales restantes y modificados", "flujos", "DEU-07",
                "Prueba del 10 % (NIIF 9 3.3.2 y B3.3.6); sin él la prueba no concluye", required=False, content=flujos),
            req("RQ-003", "Contratos de préstamo, tablas de amortización del banco y adendas", None, "DEU-02", "Condiciones, pagos y modificaciones",
                formats=("pdf", "xlsx"), use="soporte"),
            req("RQ-004", "Confirmaciones bancarias", None, "DEU-01", "Saldo confirmado, tasas, garantías y covenants", formats=("pdf",), use="soporte"),
            req("RQ-005", "Liquidaciones de desembolso con comisiones y costos de transacción", None, "DEU-03", "Importe neto recibido y TIE",
                formats=("pdf", "xlsx"), use="soporte"),
            req("RQ-006", "Cláusula del contrato que define el DSCR y demás covenants, cálculo del cliente y cartas de dispensa", None, "DEU-04",
                "Definición contractual del DSCR (el contrato manda), incumplimientos, dispensas y gracia", formats=("pdf", "xlsx"), use="soporte"),
            req("RQ-007", "Estados financieros al corte (activos, patrimonio, EBITDA, EBIT)", None, "DEU-06", "Parámetros de los ratios",
                formats=("pdf", "xlsx"), use="soporte"),
            req("RQ-008", "Mayor y auxiliares de préstamos, intereses por pagar y gasto financiero", None, "DEU-02", "Saldos registrados",
                formats=("xlsx", "pdf"), use="soporte"),
            req("RQ-009", "Garantías y refinanciaciones del ejercicio", None, "DEU-07", "Revelaciones (NIIF 7) y modificaciones (3.3.2)",
                formats=("pdf",), use="soporte", required=False),
        ],
    }


def validar_definicion(d: dict) -> dict:
    return validar_definicion_generica(d, DATASETS, PRINCIPAL)


# --- ejercicio modelo (M19) -------------------------------------------------------------

def _p(id, banco, desembolso, monto, plazo, tasa, per, sistema, saldo_reg, **x):
    return {"id": id, "banco": banco, "desembolso": desembolso, "monto": monto, "plazo": plazo, "tasa": tasa, "periodicidad": per,
            "sistema": sistema, "saldo_reg": saldo_reg, "_row": 2, **x}


def _f(id, escenario, fecha, importe, fila=2):
    return {"id": id, "escenario": escenario, "fecha": fecha, "importe": importe, "_row": fila}


_DEF_DSCR = "Flujo de caja operativo antes de intereses ÷ servicio de la deuda del ejercicio (cláusula 8.2 del contrato)"

EJEMPLO = {
    "corte": "2025-12-31",
    "parametros": {"totalActivos": 2500000, "patrimonio": 800000, "ebitda": 300000, "ebit": 220000, "efectivoServicioDeuda": 200000,
                   "baseCobertura": "EBITDA", "limDeudaActivos": 0.6, "limDeudaPatrimonio": 1.2, "limDeudaEbitda": 1.8,
                   "limCobertura": 3, "limDSCR": 1.25, "defDSCR": _DEF_DSCR},
    "datasets": {"prestamos": [
        _p("OP-101", "Banco Pichincha", "2024-01-15", "120000", "36", "11", "Mensual", "Francés", "47940.12", comisiones="2400",
           trat_comisiones="Gasto", pagos_anio="47143.75", confirmado="47940.12", int_reg="226.81", gasto_reg="7478.25"),
        _p("OP-102", "Produbanco", "2025-03-01", "200000", "60", "10", "Trimestral", "Alemán", "167760.65", comisiones="3000",
           trat_comisiones="TIE", pagos_anio="44250", confirmado="170000", gasto_reg="15010.65", cp_reg="41494.17",
           covenant="Deuda / EBITDA", incumplido="Sí", fecha_dispensa="2026-01-20", gracia_hasta="2027-06-30", fecha_covenant="2025-12-31"),
        _p("OP-103", "Banco Guayaquil", "2023-07-01", "300000", "48", "9.5", "Semestral", "Francés", "163882.07", pagos_anio="91897.18",
           confirmado="163882.07", int_reg="7742.09", gasto_reg="17317.78", cp_reg="70000", covenant="Cobertura de intereses", incumplido="No",
           modificado="Sí", fecha_modificacion="2025-12-01", comision_modificacion="1500"),
        _p("OP-104", "Banco del Pacífico", "2025-06-30", "150000", "24", "12", "Semestral", "Bullet", "145000", comisiones="1500",
           trat_comisiones="TIE", pagos_anio="9000", confirmado="150000", int_reg="49.45", gasto_reg="9392.86"),
        _p("OP-105", "Corporación Financiera Nacional", "2022-01-01", "80000", "60", "8", "Mensual", "Francés", "20135.32",
           pagos_anio="19465.34", confirmado="20135.32", int_reg="129.91", gasto_reg="2250.69", cp_reg="18653.85",
           covenant="Deuda / patrimonio", incumplido="Sí", fecha_dispensa="2025-12-15", gracia_hasta="2027-03-31", fecha_covenant="2025-12-31",
           modificado="Sí"),   # declara adenda pero no entrega los flujos: la prueba del 10 % queda bloqueada
        _p("OP-106", "Banco Internacional", "2025-10-01", "50000", "12", "13", "Mensual", "Francés", "42109.09", pagos_anio="8931.73",
           confirmado="42109.09", int_reg="441.47", gasto_reg="1482.29", cp_reg="42550.56"),
        _p("OP-107", "Banco Bolivariano", "2024-07-01", "100000", "36", "10.5", "Trimestral", "Alemán", "57958.23", comisiones="1000",
           trat_comisiones="TIE", pagos_anio="40000", confirmado="58333.33", int_reg="1514.61", gasto_reg="7881.20", cp_reg="34938.20",
           covenant="DSCR", fecha_covenant="2026-06-30"),
        _p("OP-108", "Banco Pichincha", "2026-01-10", "90000", "24", "11", "Mensual", "Francés", "0"),
    ], "flujos": [
        # OP-103: adenda del 1-12-2025. «Original» = las 4 cuotas semestrales que restaban (45.948,59 cada una);
        # «Modificado» = 6 cuotas de 30.000 con un semestre de gracia. Con estos dos escenarios la prueba concluye.
        _f("OP-103", "Original", "2026-01-01", "45948.59", 2), _f("OP-103", "Original", "2026-07-01", "45948.59", 3),
        _f("OP-103", "Original", "2027-01-01", "45948.59", 4), _f("OP-103", "Original", "2027-07-01", "45948.59", 5),
        _f("OP-103", "Modificado", "2027-01-01", "30000", 6), _f("OP-103", "Modificado", "2027-07-01", "30000", 7),
        _f("OP-103", "Modificado", "2028-01-01", "30000", 8), _f("OP-103", "Modificado", "2028-07-01", "30000", 9),
        _f("OP-103", "Modificado", "2029-01-01", "30000", 10), _f("OP-103", "Modificado", "2029-07-01", "30000", 11),
    ]},
}

_BASE = EJEMPLO["parametros"]
_SIN_DEF_DSCR = {k: v for k, v in _BASE.items() if k != "defDSCR"}
ESCENARIOS = [
    ("niif_completas", EJEMPLO["datasets"], {**_BASE, "_marco": "NIIF completas"}, EJEMPLO["corte"]),
    ("pymes_2015", EJEMPLO["datasets"], {**_BASE, "_marco": "NIIF para las PYMES", "_edicion": "2015"}, EJEMPLO["corte"]),
    ("pymes_2025", EJEMPLO["datasets"], {**_BASE, "_marco": "NIIF para las PYMES", "_edicion": "2025"}, EJEMPLO["corte"]),
    ("sin_datos_entidad", EJEMPLO["datasets"], {"_marco": "NIIF completas"}, EJEMPLO["corte"]),       # M22: ratios vacíos
    ("niif18_ebit", EJEMPLO["datasets"], {**_BASE, "baseCobertura": "EBIT", "patrimonio": -50000, "_marco": "NIIF completas"}, "2027-12-31"),
    # (B) DSCR analítico de la firma: sin definición contractual no concluye incumplimiento del covenant.
    ("dscr_analitico", EJEMPLO["datasets"], {**_SIN_DEF_DSCR, "_marco": "NIIF completas"}, EJEMPLO["corte"]),
    # (B) DSCR contractual con el denominador que define el contrato.
    ("dscr_contractual_denominador", EJEMPLO["datasets"],
     {**_BASE, "servicioDSCRContrato": 150000, "_marco": "NIIF completas"}, EJEMPLO["corte"]),
    # (A) sin el anexo de flujos: la prueba del 10 % queda bloqueada en los dos préstamos con adenda.
    ("sin_flujos_adenda", {"prestamos": EJEMPLO["datasets"]["prestamos"]}, {**_BASE, "_marco": "NIIF completas"}, EJEMPLO["corte"]),
]

# Cifras de control resueltas a mano (corte 31-12-2025):
# · OP-101 francés 120.000 al 11 % nominal (0,9167 % mensual), 36 cuotas: cuota = 120.000 × i ÷ (1 − (1 + i)^−36) = 3.928,65.
#   Tras 23 cuotas el capital es 47.940,12; interés devengado del 15 al 31-dic = 47.940,12 × i × 16/31 = 226,81.
#   Comisión 2.400 llevada a gasto: TIE anual 13,13 %; costo por amortizar al corte 379,36.
# · OP-102 alemán 200.000, 20 trimestres al 10 %: capital 10.000 por trimestre; pagos 2025 = 15.000 + 14.750 + 14.500 = 44.250;
#   interés devengado 1-dic a 31-dic = 170.000 × 2,5 % × 30/90 = 1.416,67 (no registrado). Covenant incumplido y dispensa del
#   20-01-2026 (posterior al corte): toda la deuda es corriente (NIC 1 74).
# · OP-104 bullet 150.000 al 12 % semestral: interés 9.000 por semestre; devengo del 30 al 31-dic = 150.000 × 6 % × 1/182 = 49,45.
# · DSCR = 200.000 ÷ 262.333,83 = 0,76 < 1,25 → OP-107 incumple el límite, pero su covenant se mide el 30-06-2026,
#   después del corte: NIC 1 72B → NO reclasifica (queda con la porción por vencimiento) y exige la revelación del 76ZA.
#   Alemán 100.000 en 12 trimestres = 8.333,33 de capital cada uno; al corte van 5 cuotas (capital 58.333,33) y a los
#   12 meses irán 9 (capital 25.000): capital corriente 33.333,33 + interés a la TIE devengado 1.604,87 = 34.938,20
#   (igual a la porción corriente que registró el cliente). Antes de la regla 72B: corriente 420.257,92 / no corriente
#   239.707,28; ahora: corriente 395.633,02 / no corriente 264.332,18 (pasan 24.624,90) y reclasificación por covenants 127.760,65
#   (antes 152.385,55), que corresponde solo a OP-102 (169.254,82 − 41.494,17).
# · OP-102 y OP-105 informan fecha de medición al corte (31-12-2025): su tratamiento no cambia. OP-103 no la informa:
#   se mantiene el tratamiento actual y se pide el dato (COVENANT_SIN_FECHA_MEDICION).
# · (A) Prueba del 10 % de OP-103 (adenda del 1-12-2025; NIIF 9 3.3.2 y B3.3.6). TIE anual original = 1,0475² − 1 =
#   9,725625 % (semestral 4,75 %, sin comisiones). Días desde el 1-12-2025: 31, 212, 396 y 577 para las 4 cuotas
#   originales de 45.948,59, y 396, 577, 761, 943, 1.127 y 1.308 para las 6 cuotas de 30.000 de la adenda.
#   VP originales = 170.350,33; VP modificados = 145.394,68; + comisiones 1.500 = 146.894,68. Diferencia −23.455,66
#   = −13,7691 % → |13,77 %| ≥ 10 % → condiciones sustancialmente diferentes (MODIFICACION_SUSTANCIAL). El pasivo
#   auditado NO cambia (659.965,19): el módulo no remide después de la modificación.
# · OP-105 declara adenda y no entrega flujos: la prueba queda vacía y se emite «dato insuficiente: conclusión
#   bloqueada» (MODIFICACION_DATO_INSUFICIENTE). Nunca se concluye «no sustancial» por omisión.
# · (B) DSCR = 200.000 ÷ 262.333,83 = 0,76. Con la definición contractual informada concluye «No cumple» y, sin el
#   escudo del 72B, OP-107 sería toda corriente (420.257,92). Sin definición contractual es el «DSCR analítico de la
#   firma»: no concluye (cumple vacío), OP-107 queda con incump = No y su porción corriente por vencimiento
#   34.938,20 (corriente 395.633,02 / no corriente 264.332,18).
