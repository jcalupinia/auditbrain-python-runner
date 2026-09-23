"""Cuentas por cobrar y deterioro: cartera, cobros, circularización y costo amortizado.

Una sola población (la cartera por factura al corte) alimenta siete pruebas:

1. Aging: días de mora al corte y tramo (corriente, 1–30, 31–60, 61–90, 91–180,
   181–360, más de 360).
2. Cobros posteriores (NIA 505/500): cobro aplicable = cobro con fecha posterior
   al corte, hasta el saldo; la cartera vencida sin cobro posterior se señala.
3. Circularización (NIA 505): saldo confirmado − saldo en libros por factura.
4. Corte de ventas (NIIF 15 31 y 38): período de registro (fecha de emisión) vs
   período de despacho (transferencia del control).
5. Costo amortizado e intereses implícitos (NIIF 9 5.1.1 y B5.1.1 —5.1.3 solo para
   cuentas sin componente de financiación significativo o cuando se aplica la solución práctica de NIIF 15.63—, 5.4.1; NIIF 15 60–63;
   PYMES 2015 11.13 / 2025 11.13A–11.13B y 23.38): si el plazo de crédito supera el umbral de financiación, la
   cuenta se mide al valor presente del cobro a la tasa de mercado; la TIE es esa
   tasa (un solo cobro al vencimiento) y el interés por devengar = nominal − costo
   amortizado al corte.
6. Deterioro con una matriz de tasas por tramo que fija el auditor, sobre el costo
   amortizado. NIIF completas: pérdida crediticia esperada (5.5.15, B5.5.35),
   tasa en todos los tramos, incluido el corriente. PYMES: pérdida incurrida
   (11.21–11.26), solo con evidencia objetiva: mora (11.22 b) y, en el tramo
   corriente, datos observables de una disminución medible de los flujos del
   grupo (11.22 e, evaluación por grupos 11.24). El tramo corriente conserva la
   tasa que fija el auditor y se le exige el sustento; no se fuerza a 0 %.
7. Deterioro requerido vs registrado (ajuste) y ajuste por financiación no
   reconocida; asientos propuestos.

La medición histórica completa la hacen las otras dos herramientas del rubro:
``pce_simplificada_niif9`` (NIIF 9 con historia y escenarios) y
``perdidas_incurridas_s11`` (PYMES con migración histórica).
"""
from __future__ import annotations

from backend.app.aud.niif.procesadores.base import (  # noqa: F401  (a_num y filas_mapeadas los usa el ciclo)
    FILA0, MARCO_COMPLETAS, MARCO_PYMES, a_num, campo, edicion_pymes, es_pymes, fecha, filas_mapeadas, fx, hoja, m,
    n2, problema, r2, ref, req, suma, validar_campos, validar_definicion_generica,
)

VERSION = "cxc_cartera 1.0"
RUBRO = "CXC"

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

_CARTERA = [
    campo("id", "N° de factura", alias=("numfac", "factura", "documento", "comprobante", "numero de factura"), ejemplo="001-001-000123"),
    campo("cliente", "Cliente", alias=("nomcli", "razon social", "nombre del cliente", "deudor"), ejemplo="Comercial Alfa S.A."),
    campo("emision", "Fecha de emisión (registro)", "date", alias=("emision", "fecha emision", "fecemi", "fecha factura"), ejemplo="2025-12-10"),
    campo("vence", "Fecha de vencimiento", "date", alias=("vencimiento", "fecha vencimiento", "fecvto"), ejemplo="2026-01-09"),
    campo("saldo", "Saldo por cobrar", "number", alias=("saldo pendiente", "por cobrar", "pendiente", "saldo actual"), ejemplo="12000.00"),
    campo("importe", "Importe facturado", "number", False, ("monto factura", "valor factura", "valor original")),
    campo("cobro", "Cobro posterior al cierre", "number", False, ("cobro posterior", "cobrado", "recaudo posterior")),
    campo("fecha_cobro", "Fecha del cobro", "date", False, ("fecha cobro", "fecha de cobro", "fecha recaudo")),
    campo("confirmado", "Saldo confirmado", "number", False, ("saldo confirmado", "confirmacion", "circularizacion")),
    campo("despacho", "Fecha de despacho", "date", False, ("fecha despacho", "fecha entrega", "guia de remision")),
    campo("tasa_individual", "Tasa individual % (opcional)", "number", False, ("tasa individual", "tasa especifica")),
    campo("ruc", "RUC / identificación", "text", False, ("cedula", "identificacion", "codigo cliente")),
]
CAMPOS = {"cartera": _CARTERA}
TIPOS = {"cartera": "cartera"}
DATASETS = tuple(TIPOS)
PRINCIPAL = "cartera"
CONTROL = "saldo"

PARAMETROS = {"tasaMercado": None, "plazoFinanciacion": 12, "provisionRegistrada": None, "descuentoRegistrado": None, "tasas": {}}
PARAM_NEGATIVOS = ()
ETIQUETAS_PARAM = {
    "tasaMercado": "Tasa de mercado anual para el valor presente (%)",
    "plazoFinanciacion": "Plazo de crédito que se considera financiación (meses)",
    "provisionRegistrada": "Deterioro registrado al cierre (mayor)",
    "descuentoRegistrado": "Intereses implícitos por devengar registrados (mayor)",
}
TOTAL_EJEMPLO = "deterioroRequerido"

CEDULAS = [
    ("01_Resumen", "Resumen"), ("02_Parametros", "Parámetros"), ("03_Detalle", "Detalle por factura"),
    ("04_Aging", "Antigüedad de la cartera"), ("05_Cobros_posteriores", "Cobros posteriores al cierre"),
    ("06_Circularizacion", "Circularización"), ("07_Corte_ventas", "Corte de ventas"),
    ("08_Costo_amortizado", "Costo amortizado e intereses implícitos"), ("09_Matriz_deterioro", "Matriz de deterioro"),
    ("10_Ajuste", "Deterioro requerido vs registrado"), ("11_Asientos", "Asientos propuestos"),
    ("12_Problemas", "Problemas encontrados"),
]


def kind(dataset: str) -> str:
    return TIPOS[dataset]


def validar_filas(tipo: str, filas: list) -> dict:
    r = validar_campos(CAMPOS[tipo], filas)
    for f in filas:
        ti = a_num(f.get("tasa_individual")) if str(f.get("tasa_individual", "") or "").strip() else None
        if ti is not None and not 0 <= ti <= 100:
            r["errors"].append({"row": f.get("_row"), "field": "tasa_individual", "message": "Tasa individual: use un porcentaje entre 0 y 100."})
    r["ok"] = not r["errors"]
    return r


# --- cálculo -----------------------------------------------------------------

def _opc(f, k):
    v = str(f.get(k, "") or "").strip()
    return a_num(v) if v else None


def _tramo(dv):
    return next(t for t in TRAMOS if t["min"] <= dv <= t["max"])


def _pnum(p, k):
    v = p.get(k)
    return None if v is None or str(v).strip() == "" else float(a_num(v))


def ejecutar(datasets: dict, parametros: dict, corte: str) -> dict:
    p = {**PARAMETROS, **{k: v for k, v in (parametros or {}).items() if v is not None and v != ""}}
    corte_a = fecha(corte)
    if corte_a is None:
        raise ValueError("Indique la fecha de corte del encargo.")
    pymes = es_pymes(p)
    tm = _pnum(p, "tasaMercado")
    umbral = _pnum(p, "plazoFinanciacion")
    if umbral is None or umbral < 0:
        raise ValueError("Indique el plazo de crédito que se considera financiación (meses).")
    if tm is not None and tm < 0:
        raise ValueError("La tasa de mercado no puede ser negativa.")
    prov_reg = _pnum(p, "provisionRegistrada")
    desc_reg = _pnum(p, "descuentoRegistrado")

    # Tasas por tramo (%). PYMES: el tramo corriente conserva la tasa observada o la que fije el auditor;
    # la pérdida incurrida la admite con evidencia objetiva de grupo (11.22 e) evaluada por grupos (11.24).
    manual = {k: float(a_num(v)) for k, v in (p.get("tasas") or {}).items() if k in NOMBRE_TRAMO and a_num(v) is not None}
    tasas = {t["k"]: manual.get(t["k"]) for t in TRAMOS}
    corriente_pymes = pymes and tasas["pv"] not in (None, 0.0)
    for k, v in tasas.items():
        if v is not None and not 0 <= v <= 100:
            raise ValueError(f"Tasa de {NOMBRE_TRAMO[k]}: use un porcentaje entre 0 y 100.")

    filas = []
    for f in datasets.get("cartera") or []:
        saldo = a_num(f.get("saldo"))
        emision, vence = fecha(f.get("emision")), fecha(f.get("vence"))
        if saldo is None or saldo == 0:
            continue
        if emision is None or vence is None:
            raise ValueError(f"Factura {f.get('id')}: faltan las fechas de emisión o vencimiento.")
        dv = (corte_a - vence).days
        plazo = (vence - emision).days
        financia = saldo > 0 and plazo > umbral * 365 / 12
        por_vencer = max((vence - corte_a).days, 0)
        ca = saldo / (1 + tm / 100) ** (por_vencer / 365) if financia and tm is not None else saldo
        interes = None if financia and tm is None else saldo - ca
        ti = _opc(f, "tasa_individual")
        t = _tramo(dv)
        tasa_tramo = None if tasas[t["k"]] is None else tasas[t["k"]] / 100
        tasa = ti / 100 if ti is not None else tasa_tramo
        det = None if tasa is None else max(ca * tasa, 0)
        cobro, fcobro = _opc(f, "cobro"), fecha(f.get("fecha_cobro"))
        aplicable = 0 if cobro is None or fcobro is None else (min(cobro, saldo) if fcobro > corte_a else 0)
        pendiente = saldo - aplicable
        despacho = fecha(f.get("despacho"))
        importe = _opc(f, "importe")
        filas.append({
            "factura": str(f.get("id", "")).strip(), "cliente": str(f.get("cliente", "")).strip() or "(sin nombre)",
            "emision": emision, "vence": vence, "saldo": saldo, "importe": importe, "dv": dv, "tramo": t["k"], "plazo": plazo,
            "financia": financia, "porVencer": por_vencer, "ca": ca, "interes": interes, "tasaInd": ti, "tasa": tasa, "det": det,
            "cobro": cobro, "fechaCobro": fcobro, "aplicable": aplicable, "pendiente": pendiente,
            "vencidaSinCobro": dv > 0 and pendiente > 0, "cobroNoPosterior": cobro is not None and (fcobro is None or fcobro <= corte_a),
            "confirmado": _opc(f, "confirmado"), "despacho": despacho,
            "registrada": emision <= corte_a, "despachada": despacho is not None and despacho <= corte_a,
            "_row": f.get("_row"),
        })
    if not filas:
        raise ValueError("Cargue la cartera por factura al corte del ejercicio.")

    for x in filas:
        x["importeCorte"] = x["importe"] if x["importe"] is not None else x["saldo"]
        x["errorCorte"] = x["despacho"] is not None and x["registrada"] != x["despachada"]
        x["difConf"] = None if x["confirmado"] is None else x["confirmado"] - x["saldo"]
        if x["financia"] and tm is not None:
            x["vpInicial"] = x["saldo"] / (1 + tm / 100) ** (x["plazo"] / 365)

    total = sum(x["saldo"] for x in filas)
    ca_total = sum(x["ca"] for x in filas)
    requerido = sum(x["det"] or 0 for x in filas)
    interes_req = sum(x["interes"] or 0 for x in filas)
    fin = [x for x in filas if x["financia"]]
    vp_ini = sum(x.get("vpInicial", 0) for x in fin)
    devengado = sum(x["ca"] - x["vpInicial"] for x in fin if "vpInicial" in x)
    componente = sum(x["saldo"] - x["vpInicial"] for x in fin if "vpInicial" in x)
    anticipado = sum(x["importeCorte"] for x in filas if x["errorCorte"] and x["registrada"])
    omitido = sum(x["importeCorte"] for x in filas if x["errorCorte"] and not x["registrada"])
    sin_cobro = sum(x["pendiente"] for x in filas if x["vencidaSinCobro"])
    conf = [x for x in filas if x["confirmado"] is not None]
    dif_conf = sum(abs(x["difConf"]) for x in conf)
    ajuste = requerido - (prov_reg or 0)
    ajuste_fin = interes_req - (desc_reg or 0)

    matriz = []
    for t in TRAMOS:
        de = [x for x in filas if x["tramo"] == t["k"]]
        ca_t = sum(x["ca"] for x in de)
        det_t = sum(x["det"] or 0 for x in de)
        matriz.append({"k": t["k"], "tramo": t["n"], "docs": len(de), "saldo": sum(x["saldo"] for x in de), "ca": ca_t,
                       "tasa": None if tasas[t["k"]] is None else tasas[t["k"]] / 100, "det": det_t,
                       "promedio": det_t / ca_t if ca_t else None,
                       "sinTasa": sum(x["ca"] for x in de if x["tasa"] is None)})

    modelo = ("Pérdida incurrida · Sección 11 (11.21–11.26)" if pymes
              else "Pérdida crediticia esperada · NIIF 9 enfoque simplificado (5.5.15, B5.5.35)")
    nombre_det = "pérdida incurrida" if pymes else "pérdida crediticia esperada"

    problemas = []
    for mt in matriz:
        if mt["sinTasa"]:
            causa = (("evidencia objetiva del grupo (11.22 e, 11.24)" if mt["k"] == "pv" else "mora con evidencia objetiva (11.22 b)") if pymes
                     else "la pérdida esperada se estima en todos los tramos (5.5.15, B5.5.35)")
            problemas.append(problema("TASA_FALTANTE", f"{mt['tramo']}: {m(mt['sinTasa'])} sin tasa; {causa}. Fije la tasa del tramo con su sustento.", mt["sinTasa"]))
    if corriente_pymes:
        pv = next(mt for mt in matriz if mt["k"] == "pv")
        problemas.append(problema("TASA_CORRIENTE_PYMES", f"PYMES: el tramo corriente lleva una tasa de {tasas['pv']:.2f} % y genera {m(pv['det'])} de pérdida incurrida. "
                                  "La Sección 11 solo reconoce la pérdida ya incurrida: documente la evidencia objetiva del grupo, es decir, los datos observables "
                                  "que indican una disminución medible de los flujos de efectivo futuros estimados del grupo de cartera, aunque todavía no pueda "
                                  "identificarse con facturas individuales (11.22 e), evaluada por grupos con características similares de riesgo crediticio (11.24). "
                                  "Sin ese sustento, el tramo corriente no lleva deterioro (11.21).", pv["det"]))
    if sin_cobro > 0.005:
        n = sum(1 for x in filas if x["vencidaSinCobro"])
        problemas.append(problema("VENCIDA_SIN_COBRO", f"{n} factura(s) vencidas al corte sin cobro posterior suficiente: {m(sin_cobro)}. "
                                  "Evalúe su recuperabilidad y la tasa aplicada (NIA 540, NIA 560).", sin_cobro))
    for x in filas:
        if x["cobroNoPosterior"]:
            problemas.append(problema("COBRO_NO_POSTERIOR", f"{x['factura']}: el cobro informado no tiene fecha posterior al corte; no se toma como cobro posterior.", x["cobro"]))
    dif = [x for x in conf if abs(x["difConf"]) > 0.005]
    if dif:
        problemas.append(problema("DIF_CIRCULARIZACION", f"{len(dif)} confirmación(es) con diferencia contra libros: "
                                  + "; ".join(f"{x['factura']} {m(x['difConf'])}" for x in dif) + ". Investigue y concilie (NIA 505 párr. 14).", dif_conf))
    if not conf:
        problemas.append(problema("SIN_CIRCULARIZACION", "No se informó ningún saldo confirmado: documente la circularización o los procedimientos alternativos (NIA 505)."))
    for x in filas:
        if x["errorCorte"]:
            tipo = "registrada en el ejercicio y despachada después del corte" if x["registrada"] else "despachada en el ejercicio y registrada después del corte"
            problemas.append(problema("ERROR_CORTE", f"{x['factura']}: venta {tipo} (NIIF 15 31 y 38).", x["importeCorte"]))
    if fin and tm is None:
        problemas.append(problema("FINANCIACION_SIN_TASA", f"{len(fin)} factura(s) con plazo mayor a {m(umbral)} meses y sin tasa de mercado: "
                                  "el costo amortizado no se pudo medir (NIIF 9 B5.1.1; PYMES 11.13).", sum(x["saldo"] for x in fin)))
    if interes_req > 0.005 and abs(ajuste_fin) > 0.005:
        problemas.append(problema("FINANCIACION_NO_RECONOCIDA", f"Intereses implícitos por devengar {m(interes_req)} frente a {m(desc_reg or 0)} registrados"
                                  + (" (dato del mayor no informado)" if desc_reg is None else "") + ": cartera de plazo largo medida por su nominal "
                                  "(NIIF 9 5.1.1 y B5.1.1; NIIF 15 60–63; PYMES 11.13).", ajuste_fin))
    neg = sum(x["saldo"] for x in filas if x["saldo"] < 0)
    if neg:
        problemas.append(problema("SALDOS_NEGATIVOS", f"Saldos acreedores en la cartera {m(neg)} (anticipos o notas de crédito): evalúe su reclasificación al pasivo.", neg))
    if prov_reg is None:
        problemas.append(problema("SIN_PROVISION_REGISTRADA", "Ingrese el deterioro registrado según el mayor para medir el ajuste."))
    if ajuste > 0.005:
        problemas.append(problema("DETERIORO_INSUFICIENTE", f"La {nombre_det} requerida ({m(requerido)}) supera el deterioro registrado ({m(prov_reg or 0)}).", ajuste))
    elif ajuste < -0.005:
        problemas.append(problema("DETERIORO_EXCESIVO", f"El deterioro registrado ({m(prov_reg or 0)}) supera la {nombre_det} requerida ({m(requerido)}).", ajuste))

    iso = lambda d: d.isoformat() if d else ""
    rows = [{"id": x["factura"], "cliente": x["cliente"], "emision": iso(x["emision"]), "vence": iso(x["vence"]), "dias": str(x["dv"]),
             "tramo": NOMBRE_TRAMO[x["tramo"]], "saldo": r2(x["saldo"]), "costoAmortizado": r2(x["ca"]),
             "tasa": "" if x["tasa"] is None else f"{x['tasa']:.6f}", "deterioro": "" if x["det"] is None else r2(x["det"]),
             "_row": x["_row"]} for x in filas]
    totales = {"saldo": total, "costoAmortizado": ca_total, "deterioroRequerido": requerido, "provisionRegistrada": prov_reg or 0,
               "ajuste": ajuste, "interesNoDevengado": interes_req, "descuentoRegistrado": desc_reg or 0, "ajusteFinanciacion": ajuste_fin,
               "corteAnticipado": anticipado, "corteOmitido": omitido, "vencidoSinCobro": sin_cobro, "difCircularizacion": dif_conf}
    etiquetas = {"saldo": "Cartera al corte (nominal)", "costoAmortizado": "Cartera a costo amortizado",
                 "deterioroRequerido": ("Pérdida incurrida requerida" if pymes else "Pérdida crediticia esperada requerida"),
                 "provisionRegistrada": "Deterioro registrado (mayor)", "ajuste": "Ajuste de deterioro propuesto",
                 "interesNoDevengado": "Intereses implícitos por devengar", "descuentoRegistrado": "Intereses por devengar registrados",
                 "ajusteFinanciacion": "Ajuste por financiación implícita", "corteAnticipado": "Ventas registradas antes del despacho",
                 "corteOmitido": "Ventas despachadas sin registrar en el ejercicio", "vencidoSinCobro": "Cartera vencida sin cobro posterior",
                 "difCircularizacion": "Diferencias de circularización (absolutas)"}
    detalle = {"cortes": {"actual": corte_a.isoformat()}, "parametros": p, "pymes": pymes, "edicion": edicion_pymes(p) if pymes else "",
               "modelo": modelo, "tasaMercado": tm, "umbral": umbral, "provisionRegistrada": prov_reg, "descuentoRegistrado": desc_reg,
               "tasasTramo": tasas, "matriz": matriz,
               "filas": [{k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in x.items()} for x in filas],
               "fin": {"vpInicial": vp_ini, "devengado": devengado, "componente": componente},
               "tasas": [{"k": mt["k"], "tramo": mt["tramo"], "tasa": mt["tasa"],
                          "origen": "Fijada por el auditor" if mt["tasa"] is not None else "Sin tasa"}
                         for mt in matriz]}
    return {"engine": VERSION, "rows": rows, "totals": {k: r2(v) for k, v in totales.items()}, "labels": etiquetas,
            "primary": "ajuste", "exceptions": problemas, "schedule": [], "detalle": detalle}


# --- cédulas con fórmulas ---------------------------------------------------------

P = ref("02_Parametros")
DET, MAT, AJ, COB, CIR, COR, CAM = (ref(n) for n in ("03_Detalle", "09_Matriz_deterioro", "10_Ajuste", "05_Cobros_posteriores",
                                                         "06_Circularizacion", "07_Corte_ventas", "08_Costo_amortizado"))
_PAR = ["corte", "marco", "modelo", "tasaMercado", "plazoFinanciacion", "provisionRegistrada", "descuentoRegistrado"] + [f"tasa_{t['k']}" for t in TRAMOS]
PAR = {k: FILA0 + i for i, k in enumerate(_PAR)}
_AJ = ["requerido", "registrado", "ajuste", "interesReq", "descReg", "ajusteFin", "anticipado", "omitido", "sinCobro", "difConf"]
AJF = {k: FILA0 + i for i, k in enumerate(_AJ)}


def _pb(k):
    return f"{P}$B${PAR[k]}"


def _tramo_formula(celda: str) -> str:
    f = f'"{TRAMOS[-1]["n"]}"'
    for t in reversed(TRAMOS[:-1]):
        f = f'IF({celda}<={t["max"]},"{t["n"]}",{f})'
    return f


def _rango(hoja_ref: str, col: str, n: int) -> str:
    return f"{hoja_ref}${col}${FILA0}:${col}${FILA0 + max(n, 1) - 1}"


def hojas(res: dict) -> list[dict]:
    d = res["detalle"]
    fl, mat = d["filas"], d["matriz"]
    t = {k: float(v) for k, v in res["totals"].items()}
    nd = len(fl)
    fin_det = FILA0 + nd - 1
    tm = _pb("tasaMercado")

    parametros = [
        ["Corte del ejercicio", d["cortes"]["actual"], "Ficha del encargo"],
        ["Marco contable", MARCO_PYMES + (f" {d['edicion']}" if d["pymes"] else "") if d["pymes"] else MARCO_COMPLETAS, "Ficha del encargo: enruta el modelo de deterioro"],
        ["Modelo de deterioro", d["modelo"], "NIIF 9 5.5.15 / PYMES 11.21–11.26"],
        ["Tasa de mercado anual para el valor presente (%)", d["tasaMercado"], "NIIF 9 B5.1.1; PYMES 11.13 — tasa de un instrumento de deuda similar"],
        ["Plazo que se considera financiación (meses)", d["umbral"], "NIIF 15 63 (solución práctica: más de 12 meses habilita evaluar la financiación con NIIF 15.60–62, no la concluye); "
                                                      "PYMES 2015 11.13 (pago diferido más allá de los términos comerciales normales) / 2025 11.13A–11.13B y 23.38 (opción: cobro dentro de un año) — juicio"],
        ["Deterioro registrado al cierre (mayor)", d["provisionRegistrada"], "Mayor contable"],
        ["Intereses implícitos por devengar registrados (mayor)", d["descuentoRegistrado"], "Mayor contable"],
    ]
    for mt in mat:
        v = d["tasasTramo"][mt["k"]]
        nota = (("PYMES: solo con evidencia objetiva del grupo (11.22 e) evaluada por grupos (11.24)" if mt["k"] == "pv"
                 else "Tasa de pérdida incurrida del tramo (11.22 b, 11.24)") if d["pymes"] else "Tasa esperada del tramo (B5.5.35)")
        parametros.append([f"Tasa · {mt['tramo']} (%)", v, nota])

    # 03 · Detalle por factura.
    detalle = []
    fin_mat = FILA0 + len(TRAMOS) - 1
    idx = lambda r: f"INDEX({MAT}$D${FILA0}:$D${fin_mat},MATCH(H{r},{MAT}$A${FILA0}:$A${fin_mat},0))"
    for i, x in enumerate(fl):
        r = FILA0 + i
        detalle.append([
            x["factura"], x["cliente"], x["emision"], x["vence"], n2(x["saldo"]), x["importe"],
            fx(f"{_pb('corte')}-D{r}", x["dv"]), fx(_tramo_formula(f"G{r}"), NOMBRE_TRAMO[x["tramo"]]), fx(f"D{r}-C{r}", x["plazo"]),
            fx(f'IF(AND(E{r}>0,I{r}>{_pb("plazoFinanciacion")}*365/12),"Sí","No")', "Sí" if x["financia"] else "No"),
            fx(f'IF(AND(J{r}="Sí",{tm}<>""),E{r}/(1+{tm}/100)^(MAX(D{r}-{_pb("corte")},0)/365),E{r})', x["ca"]),
            fx(f'IF(AND(J{r}="Sí",{tm}=""),"",E{r}-K{r})', x["interes"]),
            x["tasaInd"],
            fx(f'IF(M{r}<>"",M{r}/100,IF({idx(r)}="","",{idx(r)}))', x["tasa"]),
            fx(f'IF(N{r}="","",MAX(K{r}*N{r},0))', x["det"]),
        ])
    tot_det = ["TOTAL", "", "", "", suma("E", fin_det, t["saldo"]), None, None, "", None, "", suma("K", fin_det, t["costoAmortizado"]),
               suma("L", fin_det, t["interesNoDevengado"]), None, None, suma("O", fin_det, t["deterioroRequerido"])]

    # 04 · Aging (importe nominal).
    aging = []
    for i, mt in enumerate(mat):
        r = FILA0 + i
        aging.append([mt["tramo"], fx(f"COUNTIF({_rango(DET, 'H', nd)},A{r})", mt["docs"]),
                      fx(f"SUMIF({_rango(DET, 'H', nd)},A{r},{_rango(DET, 'E', nd)})", n2(mt["saldo"])),
                      fx(f"IF(SUM({_rango(DET, 'E', nd)})=0,\"\",C{r}/SUM({_rango(DET, 'E', nd)}))", mt["saldo"] / t["saldo"] if t["saldo"] else None),
                      "No" if mt["k"] == "pv" else "Sí"])
    fin_ag = FILA0 + len(mat) - 1

    # 05 · Cobros posteriores (todas las facturas).
    cobros = []
    for i, x in enumerate(fl):
        r = FILA0 + i
        cobros.append([x["factura"], x["cliente"], fx(f"{DET}G{r}", x["dv"]), fx(f"{DET}E{r}", n2(x["saldo"])), x["cobro"], x["fechaCobro"] or None,
                       fx(f'IF(OR(E{r}="",F{r}=""),0,IF(F{r}>{_pb("corte")},MIN(E{r},D{r}),0))', x["aplicable"]),
                       fx(f"D{r}-G{r}", x["pendiente"]),
                       fx(f'IF(AND(C{r}>0,H{r}>0),"Sí","No")', "Sí" if x["vencidaSinCobro"] else "No"),
                       fx(f'IF(I{r}="Sí",H{r},0)', x["pendiente"] if x["vencidaSinCobro"] else 0)])
    tot_cob = ["TOTAL", "", None, suma("D", fin_det, t["saldo"]), None, None, suma("G", fin_det, sum(x["aplicable"] for x in fl)),
               suma("H", fin_det, sum(x["pendiente"] for x in fl)), "", suma("J", fin_det, t["vencidoSinCobro"])]

    # 06 · Circularización (facturas con saldo confirmado).
    circ = []
    for i, x in enumerate(fl):
        if x["confirmado"] is None:
            continue
        r, rd = FILA0 + len(circ), FILA0 + i
        circ.append([x["factura"], x["cliente"], fx(f"{DET}E{rd}", n2(x["saldo"])), x["confirmado"], fx(f"D{r}-C{r}", x["difConf"]),
                     fx(f"ABS(E{r})", abs(x["difConf"])), fx(f'IF(ABS(E{r})<=0.005,"Conforme","Diferencia")', "Conforme" if abs(x["difConf"]) <= 0.005 else "Diferencia")])
    fin_cir = FILA0 + len(circ) - 1
    conf = [x for x in fl if x["confirmado"] is not None]
    tot_cir = (["TOTAL", "", suma("C", fin_cir, sum(x["saldo"] for x in conf)), suma("D", fin_cir, sum(x["confirmado"] for x in conf)),
                suma("E", fin_cir, sum(x["difConf"] for x in conf)), suma("F", fin_cir, t["difCircularizacion"]), ""] if circ else None)

    # 07 · Corte de ventas (facturas con fecha de despacho).
    corte = []
    for i, x in enumerate(fl):
        if not x["despacho"]:
            continue
        r, rd = FILA0 + len(corte), FILA0 + i
        corte.append([x["factura"], x["cliente"], x["emision"], x["despacho"],
                      fx(f'IF({DET}F{rd}<>"",{DET}F{rd},{DET}E{rd})', x["importeCorte"]),
                      fx(f'IF(C{r}<={_pb("corte")},"Sí","No")', "Sí" if x["registrada"] else "No"),
                      fx(f'IF(D{r}<={_pb("corte")},"Sí","No")', "Sí" if x["despachada"] else "No"),
                      fx(f'IF(AND(F{r}="Sí",G{r}="No"),E{r},0)', x["importeCorte"] if x["errorCorte"] and x["registrada"] else 0),
                      fx(f'IF(AND(F{r}="No",G{r}="Sí"),E{r},0)', x["importeCorte"] if x["errorCorte"] and not x["registrada"] else 0)])
    fin_cor = FILA0 + len(corte) - 1
    tot_cor = (["TOTAL", "", "", "", suma("E", fin_cor, sum(x["importeCorte"] for x in fl if x["despacho"])), "", "",
                suma("H", fin_cor, t["corteAnticipado"]), suma("I", fin_cor, t["corteOmitido"])] if corte else None)

    # 08 · Costo amortizado (facturas con financiación implícita).
    cam = []
    for i, x in enumerate(fl):
        if not x["financia"]:
            continue
        r, rd = FILA0 + len(cam), FILA0 + i
        vp = x.get("vpInicial")
        h = None if d["tasaMercado"] is None else d["tasaMercado"] / 100
        cam.append([x["factura"], x["cliente"], x["emision"], x["vence"], fx(f"{DET}E{rd}", n2(x["saldo"])),
                    fx(f"D{r}-C{r}", x["plazo"]), fx(f"MAX(D{r}-{_pb('corte')},0)", x["porVencer"]),
                    fx(f'IF({tm}="","",{tm}/100)', h),
                    fx(f'IF(H{r}="","",E{r}/(1+H{r})^(F{r}/365))', vp),
                    fx(f'IF(H{r}="","",E{r}-I{r})', None if vp is None else x["saldo"] - vp),
                    fx(f'IF(H{r}="","",E{r}/(1+H{r})^(G{r}/365))', None if vp is None else x["ca"]),
                    fx(f'IF(H{r}="","",K{r}-I{r})', None if vp is None else x["ca"] - vp),
                    fx(f'IF(H{r}="","",E{r}-K{r})', None if vp is None else x["saldo"] - x["ca"])])
    fin_cam = FILA0 + len(cam) - 1
    fi = d["fin"]
    tot_cam = (["TOTAL", "", "", "", suma("E", fin_cam, sum(x["saldo"] for x in fl if x["financia"])), None, None, None,
                suma("I", fin_cam, fi["vpInicial"]), suma("J", fin_cam, fi["componente"]), suma("K", fin_cam, sum(x["ca"] for x in fl if x["financia"] and "vpInicial" in x)),
                suma("L", fin_cam, fi["devengado"]), suma("M", fin_cam, t["interesNoDevengado"])] if cam else None)

    # 09 · Matriz de deterioro (sobre el costo amortizado).
    matriz = []
    for i, mt in enumerate(mat):
        r = FILA0 + i
        pr = _pb(f"tasa_{mt['k']}")
        matriz.append([mt["tramo"], fx(f"COUNTIF({_rango(DET, 'H', nd)},A{r})", mt["docs"]),
                       fx(f"SUMIF({_rango(DET, 'H', nd)},A{r},{_rango(DET, 'K', nd)})", mt["ca"]),
                       fx(f'IF({pr}="","",{pr}/100)', mt["tasa"]),
                       fx(f"SUMIF({_rango(DET, 'H', nd)},A{r},{_rango(DET, 'O', nd)})", mt["det"]),
                       fx(f'IF(C{r}=0,"",E{r}/C{r})', mt["promedio"])])
    tot_mat = ["TOTAL", None, suma("C", fin_mat, t["costoAmortizado"]), None, suma("E", fin_mat, t["deterioroRequerido"]), None]

    # 10 · Ajuste.
    tot_ref = lambda hoja_ref, col, fin, ok: f"{hoja_ref}{col}{fin + 1}" if ok else "0"
    nombre_det = "Pérdida incurrida requerida (Sección 11)" if d["pymes"] else "Pérdida crediticia esperada requerida (NIIF 9)"
    ajuste = [
        [nombre_det, fx(f"{MAT}E{fin_mat + 1}", t["deterioroRequerido"]), "Matriz de deterioro + tasas individuales"],
        ["Deterioro registrado (mayor)", fx(_pb("provisionRegistrada"), t["provisionRegistrada"]), "Parámetros"],
        ["Ajuste de deterioro propuesto", fx(f"B{AJF['requerido']}-B{AJF['registrado']}", t["ajuste"]), "Positivo: falta deterioro; negativo: exceso"],
        ["Intereses implícitos por devengar requeridos", fx(f"SUM({_rango(DET, 'L', nd)})", t["interesNoDevengado"]), "NIIF 9 5.1.1 y B5.1.1; PYMES 11.13"],
        ["Intereses por devengar registrados (mayor)", fx(_pb("descuentoRegistrado"), t["descuentoRegistrado"]), "Parámetros"],
        ["Ajuste por financiación implícita", fx(f"B{AJF['interesReq']}-B{AJF['descReg']}", t["ajusteFinanciacion"]), "Menor valor de la cartera"],
        ["Ventas registradas antes del despacho", fx(tot_ref(COR, "H", fin_cor, corte), t["corteAnticipado"]), "NIIF 15 31, 38"],
        ["Ventas despachadas sin registrar en el ejercicio", fx(tot_ref(COR, "I", fin_cor, corte), t["corteOmitido"]), "NIIF 15 31, 38"],
        ["Cartera vencida sin cobro posterior", fx(f"{COB}J{fin_det + 1}", t["vencidoSinCobro"]), "Evidencia sobre la estimación (NIA 540)"],
        ["Diferencias de circularización (absolutas)", fx(tot_ref(CIR, "F", fin_cir, circ), t["difCircularizacion"]), "NIA 505"],
    ]

    # 11 · Asientos (importes remiten a 10_Ajuste y 08_Costo_amortizado).
    asientos = []

    def asiento(titulo, lineas):
        for i, (cta, formula, valor, debe) in enumerate(lineas):
            v = fx(formula, n2(valor))
            asientos.append([titulo if i == 0 else "", cta, v if debe else None, None if debe else v])

    ajb = lambda k: f"{AJ}B{AJF[k]}"
    gasto = "pérdida incurrida" if d["pymes"] else "pérdidas crediticias esperadas"
    if t["ajuste"] > 0.005:
        asiento("1 · Deterioro faltante", [(f"Gasto por {gasto}", f"ABS({ajb('ajuste')})", t["ajuste"], True),
                                           ("(-) Deterioro de cuentas por cobrar", f"ABS({ajb('ajuste')})", t["ajuste"], False)])
    elif t["ajuste"] < -0.005:
        asiento("1 · Reversión del exceso de deterioro", [("(-) Deterioro de cuentas por cobrar", f"ABS({ajb('ajuste')})", -t["ajuste"], True),
                                                          ("Ingreso por reversión de deterioro", f"ABS({ajb('ajuste')})", -t["ajuste"], False)])
    if abs(t["ajusteFinanciacion"]) > 0.005 and cam and d["tasaMercado"] is not None:
        if not d["descuentoRegistrado"]:
            asiento("2 · Componente de financiación no reconocido", [
                ("Ingresos de actividades ordinarias (componente de financiación)", f"{CAM}J{fin_cam + 1}", fi["componente"], True),
                ("(-) Intereses implícitos por devengar (cartera)", f"{CAM}M{fin_cam + 1}", t["interesNoDevengado"], False),
                ("Ingresos financieros por intereses devengados", f"{CAM}L{fin_cam + 1}", fi["devengado"], False)])
        else:
            asiento("2 · Ajuste de intereses implícitos por devengar", [
                ("Ingresos financieros / de actividades ordinarias", f"ABS({ajb('ajusteFin')})", abs(t["ajusteFinanciacion"]), t["ajusteFinanciacion"] > 0),
                ("(-) Intereses implícitos por devengar (cartera)", f"ABS({ajb('ajusteFin')})", abs(t["ajusteFinanciacion"]), t["ajusteFinanciacion"] < 0)])
    if t["corteAnticipado"] > 0.005:
        asiento("3 · Reverso de ventas no despachadas al corte", [("Ingresos de actividades ordinarias", ajb("anticipado"), t["corteAnticipado"], True),
                                                                   ("Cuentas por cobrar comerciales", ajb("anticipado"), t["corteAnticipado"], False)])
    if t["corteOmitido"] > 0.005:
        asiento("4 · Ventas despachadas no registradas", [("Cuentas por cobrar comerciales", ajb("omitido"), t["corteOmitido"], True),
                                                          ("Ingresos de actividades ordinarias", ajb("omitido"), t["corteOmitido"], False)])

    ref_res = {"saldo": f"SUM({_rango(DET, 'E', nd)})", "costoAmortizado": f"SUM({_rango(DET, 'K', nd)})",
               "deterioroRequerido": ajb("requerido"), "provisionRegistrada": ajb("registrado"), "ajuste": ajb("ajuste"),
               "interesNoDevengado": ajb("interesReq"), "descuentoRegistrado": ajb("descReg"), "ajusteFinanciacion": ajb("ajusteFin"),
               "corteAnticipado": ajb("anticipado"), "corteOmitido": ajb("omitido"), "vencidoSinCobro": ajb("sinCobro"),
               "difCircularizacion": ajb("difConf")}
    resumen = [[res["labels"][k], fx(ref_res[k], t[k])] for k in res["labels"]]

    return [
        hoja("01_Resumen", "Resumen", [["Concepto", "t"], ["Importe", "n"]], resumen),
        hoja("02_Parametros", "Parámetros", [["Parámetro", "t"], ["Valor", "x"], ["Sustento", "t"]], parametros),
        hoja("03_Detalle", "Detalle por factura",
             [["Factura", "t"], ["Cliente", "t"], ["Emisión", "d"], ["Vencimiento", "d"], ["Saldo", "n"], ["Importe facturado", "n"],
              ["Días de mora", "i"], ["Tramo", "t"], ["Plazo de crédito (días)", "i"], ["Financiación implícita", "t"],
              ["Costo amortizado", "n"], ["Interés implícito por devengar", "n"], ["Tasa individual (%)", "x"], ["Tasa aplicada", "p"],
              ["Deterioro requerido", "n"]], detalle, tot_det),
        hoja("04_Aging", "Antigüedad de la cartera", [["Tramo", "t"], ["Facturas", "i"], ["Saldo", "n"], ["% de la cartera", "p"], ["Vencido", "t"]],
             aging, ["TOTAL", suma("B", fin_ag, len(fl)), suma("C", fin_ag, t["saldo"]), None, ""]),
        hoja("05_Cobros_posteriores", "Cobros posteriores al cierre",
             [["Factura", "t"], ["Cliente", "t"], ["Días de mora", "i"], ["Saldo al corte", "n"], ["Cobro informado", "n"], ["Fecha del cobro", "d"],
              ["Cobro posterior aplicable", "n"], ["Saldo sin cobro posterior", "n"], ["Vencida sin cobro", "t"], ["Vencido sin cobro", "n"]], cobros, tot_cob),
        hoja("06_Circularizacion", "Circularización",
             [["Factura", "t"], ["Cliente", "t"], ["Saldo en libros", "n"], ["Saldo confirmado", "n"], ["Diferencia", "n"], ["Diferencia absoluta", "n"], ["Estado", "t"]],
             circ, tot_cir),
        hoja("07_Corte_ventas", "Corte de ventas",
             [["Factura", "t"], ["Cliente", "t"], ["Emisión (registro)", "d"], ["Despacho", "d"], ["Importe", "n"], ["Registrada en el ejercicio", "t"],
              ["Despachada en el ejercicio", "t"], ["Registrada antes del despacho", "n"], ["Despachada sin registrar", "n"]], corte, tot_cor),
        hoja("08_Costo_amortizado", "Costo amortizado e intereses implícitos",
             [["Factura", "t"], ["Cliente", "t"], ["Emisión", "d"], ["Vencimiento", "d"], ["Nominal", "n"], ["Plazo (días)", "i"], ["Días por vencer", "i"],
              ["TIE = tasa de mercado", "p"], ["Valor presente inicial (ingreso)", "n"], ["Componente de financiación", "n"],
              ["Costo amortizado al corte", "n"], ["Interés devengado al corte", "n"], ["Interés por devengar", "n"]], cam, tot_cam),
        hoja("09_Matriz_deterioro", "Matriz de deterioro",
             [["Tramo", "t"], ["Facturas", "i"], ["Costo amortizado", "n"], ["Tasa del tramo", "p"], ["Deterioro requerido", "n"], ["Tasa promedio aplicada", "p"]],
             matriz, tot_mat),
        hoja("10_Ajuste", "Deterioro requerido vs registrado", [["Concepto", "t"], ["Importe", "n"], ["Referencia", "t"]], ajuste),
        hoja("11_Asientos", "Asientos propuestos", [["Asiento", "t"], ["Cuenta", "t"], ["Debe", "n"], ["Haber", "n"]], asientos),
        hoja("12_Problemas", "Problemas encontrados", [["Código", "t"], ["Descripción", "t"], ["Importe", "n"]],
             [[e["code"], e["message"], n2(e["amount"])] for e in res["exceptions"]]),
    ]


# --- definición -----------------------------------------------------------------

def definicion() -> dict:
    cartera = ("Una fila por factura: N° de factura, cliente, emisión, vencimiento y saldo; y, cuando existan, importe facturado, "
               "cobro posterior y su fecha, saldo confirmado por el cliente, fecha de despacho y tasa individual. Sin filas de total.")
    return {
        "name": "Cuentas por cobrar y deterioro · cartera, cobros, circularización y costo amortizado",
        "area": "Cuentas por cobrar",
        "processor": "cxc_cartera",
        "frameworks": [MARCO_COMPLETAS, MARCO_PYMES],
        "summary": ("Recalcula la antigüedad de la cartera, contrasta cobros posteriores, confirmaciones y corte de ventas, mide al costo "
                    "amortizado la cartera con financiación implícita (valor presente a la tasa de mercado) y compara el deterioro "
                    "requerido por una matriz de tasas por tramo con el registrado. En NIIF completas el deterioro es pérdida crediticia "
                    "esperada (NIIF 9 5.5.15, B5.5.35, incluido el tramo corriente); en PYMES es pérdida incurrida (Sección 11, solo con "
                    "evidencia objetiva: mora 11.22 b o datos observables del grupo 11.22 e evaluados por grupos 11.24). Para medir las tasas con la historia completa existen las herramientas «Pérdida crediticia "
                    "esperada · enfoque simplificado (NIIF 9)» y «Deterioro de cuentas por cobrar · pérdidas incurridas (PYMES)»."),
        "source": {"organization": "IFRS Foundation (texto en español: Reglamento (UE) 2023/1803)",
                   "type": "Norma contable", "date": "",
                   "document": ("NIIF 9 párr. 5.1.1 y B5.1.1 (5.1.3 solo para cuentas sin componente de financiación significativo o cuando se aplica la solución práctica de NIIF 15.63), 5.4.1, "
                                "5.5.15 (con componente de financiación significativo, 5.5.15 a) ii) solo si esa es la política de la entidad), "
                                "B5.5.35; NIIF 15 párr. 31, 38, 60–63 (63, solución práctica: más de 12 meses habilita evaluar la "
                                "financiación con NIIF 15.60–62, no la concluye); NIIF 7 párr. 35H, 35M y 35N"),
                   "url": "https://eur-lex.europa.eu/legal-content/ES/TXT/HTML/?uri=CELEX:32023R1803"},
        "source_pymes": {"organization": "IFRS Foundation", "type": "Norma contable", "date": "",
                         "document": ("NIIF para las PYMES 2015, Sección 11 · párr. 11.13 (financiación = pago diferido más allá de los términos "
                                      "comerciales normales: valor presente a la tasa de mercado), 11.21–11.26 (pérdida incurrida). "
                                      "Edición 2025: financiación en párr. 11.13A–11.13B y 23.38 (opción: cobro dentro de un año)."),
                         "url": "https://www.ifrs.org/issued-standards/ifrs-for-smes/"},
        "nia": [
            {"document": "NIA 505", "section": "párr. 7, 12, 14 y 16", "requirement": "Confirmaciones externas: controlar las solicitudes, aplicar procedimientos alternativos ante cada no respuesta, investigar las diferencias y evaluar la evidencia obtenida."},
            {"document": "NIA 500", "section": "párr. 9", "requirement": "Evaluar exactitud e integridad del anexo de cartera contra el mayor."},
            {"document": "NIA 540 (Revisada)", "section": "párr. 13, 16–30 y 32", "requirement": "El deterioro es una estimación: evaluar método, datos, supuestos (tasas por tramo, tasa de mercado) y sesgo."},
            {"document": "NIA 560", "section": "párr. 6 y NIA 540 párr. 21", "requirement": "Cobros posteriores al cierre como evidencia sobre la recuperabilidad."},
            {"document": "NIA 330", "section": "párr. 18", "requirement": "Procedimientos sustantivos de corte y existencia sobre saldos materiales."},
        ],
        "calculo": [
            "Aging: días de mora = corte − vencimiento; tramos corriente, 1–30, 31–60, 61–90, 91–180, 181–360 y más de 360 días.",
            "Cobros posteriores: cobro aplicable = cobro con fecha posterior al corte, hasta el saldo; cartera vencida sin cobro = saldo − cobro aplicable.",
            "Circularización: diferencia = saldo confirmado − saldo en libros, por factura.",
            "Corte de ventas: la venta pertenece al período del despacho (NIIF 15 31 y 38); se compara con el período de registro (fecha de emisión).",
            "Financiación implícita: plazo de crédito (vencimiento − emisión) mayor al umbral (12 meses por defecto; NIIF 15 63: superarlo habilita evaluar la financiación con NIIF 15.60–62, no la concluye; PYMES 2015 11.13 / 2025 11.13A–11.13B y 23.38).",
            "Costo amortizado al corte = nominal ÷ (1 + tasa de mercado)^(días por vencer ÷ 365); TIE = tasa de mercado (un solo cobro al vencimiento, 5.4.1); interés por devengar = nominal − costo amortizado.",
            "Deterioro requerido = costo amortizado × tasa del tramo (o tasa individual). NIIF completas: tasas esperadas en todos los tramos (5.5.15, B5.5.35). PYMES: pérdida ya incurrida con evidencia objetiva (11.21); la tasa del tramo corriente no se fuerza a 0 % —se conserva la observada o la que fije el auditor— y se exige el sustento de la evidencia objetiva del grupo (11.22 e) evaluada por grupos (11.24).",
            "Ajuste = deterioro requerido − deterioro registrado; ajuste por financiación = interés por devengar requerido − registrado.",
        ],
        "fields": _CARTERA, "rules": [], "control": CONTROL, "primary": "ajuste",
        "campos": CAMPOS, "tipos": TIPOS, "parametros": {k: v for k, v in PARAMETROS.items() if k != "tasas"},
        "etiquetas_parametros": ETIQUETAS_PARAM, "tramos": [{"k": t["k"], "tramo": t["n"]} for t in TRAMOS],
        "cedulas": [[n, l] for n, l in CEDULAS],
        "program": [
            {"code": "CXCCAR-01", "objective": "Integridad y antigüedad de la cartera", "risk": "Anexo incompleto o antigüedad mal calculada", "assertion": "Integridad",
             "procedure": "Conciliar la cartera por factura con el mayor y recalcular la antigüedad al corte", "evidence": "Cartera por factura y mayor",
             "criterion": "Diferencia dentro de tolerancia; antigüedad recalculada", "source": "NIA 500 párr. 9"},
            {"code": "CXCCAR-02", "objective": "Cobros posteriores", "risk": "Cartera vencida no recuperable", "assertion": "Valoración / Existencia",
             "procedure": "Cotejar cobros posteriores al cierre con la cartera, en especial la vencida", "evidence": "Estados de cuenta bancarios y recibos posteriores",
             "criterion": "Vencido sin cobro evaluado en el deterioro", "source": "NIA 560 párr. 6 · NIA 540 párr. 21"},
            {"code": "CXCCAR-03", "objective": "Circularización", "risk": "Saldos inexistentes o mal medidos", "assertion": "Existencia",
             "procedure": "Enviar confirmaciones, comparar saldo confirmado con libros e investigar diferencias", "evidence": "Respuestas de clientes",
             "criterion": "Diferencias conciliadas o ajustadas", "source": "NIA 505"},
            {"code": "CXCCAR-04", "objective": "Corte de ventas", "risk": "Ventas registradas en un período distinto al despacho", "assertion": "Corte",
             "procedure": "Comparar fecha de factura con fecha de despacho alrededor del cierre", "evidence": "Guías de remisión, facturas",
             "criterion": "Ventas en el período de la transferencia del control", "source": "NIIF 15 31, 38 · NIA 330"},
            {"code": "CXCCAR-05", "objective": "Costo amortizado e intereses implícitos", "risk": "Cartera de plazo largo medida por su nominal", "assertion": "Valoración",
             "procedure": "Identificar facturas con plazo mayor al umbral y medir su valor presente a la tasa de mercado", "evidence": "Contratos, pagarés, tasas de mercado",
             "criterion": "Componente de financiación reconocido", "source": "NIIF 9 5.1.1, B5.1.1 y 5.4.1 (5.1.3 solo sin componente de financiación significativo o con la solución práctica de NIIF 15.63) · NIIF 15 60–63 · PYMES 2015 11.13 / 2025 11.13A–11.13B y 23.38"},
            {"code": "CXCCAR-06", "objective": "Deterioro requerido vs registrado", "risk": "Deterioro insuficiente", "assertion": "Valoración",
             "procedure": "Aplicar la matriz de tasas por tramo y las tasas individuales y comparar con el deterioro registrado", "evidence": "Matriz de tasas, política de crédito",
             "criterion": "Ajuste cuantificado", "source": "NIIF 9 5.5.15 (con componente de financiación significativo, 5.5.15 a) ii) solo si esa es la política de la entidad), B5.5.35 · PYMES 11.21–11.26 (11.22 b, 11.22 e y 11.24) · NIA 540"},
            {"code": "CXCCAR-07", "objective": "Revelación", "risk": "Nota de riesgo de crédito incompleta", "assertion": "Presentación",
             "procedure": "Preparar la antigüedad y el movimiento del deterioro para las notas", "evidence": "Aging, mayor del deterioro",
             "criterion": "Nota completa", "source": "NIIF 7 35H, 35M y 35N"},
        ],
        "requests": [
            req("RQ-001", "Cartera por factura al corte con cobros posteriores, confirmaciones y despachos", "cartera", "CXCCAR-01",
                "Población a medir y conciliar con el mayor", content=cartera),
            req("RQ-002", "Mayor de cuentas por cobrar, deterioro y descuentos al corte", None, "CXCCAR-06", "Deterioro e intereses registrados",
                formats=("xlsx", "pdf"), use="soporte"),
            req("RQ-003", "Respuestas de confirmación de clientes", None, "CXCCAR-03", "Sustento del saldo confirmado", formats=("pdf",), use="soporte"),
            req("RQ-004", "Estados de cuenta y recibos de cobros posteriores al cierre", None, "CXCCAR-02", "Sustento de los cobros posteriores",
                formats=("pdf", "xlsx"), use="soporte"),
            req("RQ-005", "Guías de remisión de las ventas alrededor del cierre", None, "CXCCAR-04", "Sustento de la fecha de despacho",
                formats=("pdf", "xlsx"), use="soporte", required=False),
            req("RQ-006", "Contratos o pagarés de ventas a plazo y sustento de la tasa de mercado", None, "CXCCAR-05", "Financiación implícita",
                formats=("pdf", "docx"), use="soporte", required=False),
            req("RQ-007", "Política de crédito y sustento de las tasas de deterioro por tramo", None, "CXCCAR-06", "Sustento de la matriz",
                formats=("pdf", "docx", "xlsx"), use="soporte"),
        ],
    }


def validar_definicion(d: dict) -> dict:
    return validar_definicion_generica(d, DATASETS, PRINCIPAL)


# --- ejemplo de control (M19) -------------------------------------------------------

def _ej(id, cliente, emision, vence, saldo, **extra):
    return {"id": id, "cliente": cliente, "emision": emision, "vence": vence, "saldo": saldo, "_row": 2, **extra}


# Corte 2025-12-31, tasa de mercado 10 %, umbral 12 meses, deterioro registrado 2.000.
# F-008: 20.000 a 730 días, 547 por vencer → costo amortizado 20.000 ÷ 1,1^(547/365) = 17.337,95;
# interés por devengar 2.662,05; valor presente inicial 20.000 ÷ 1,21 = 16.528,93.
# F-004: 61 días (tramo 61–90, 15 %) × 4.000 = 600; confirmado 3.500 → diferencia −500.
EJEMPLO = {
    "corte": "2025-12-31",
    "parametros": {"_marco": MARCO_COMPLETAS, "tasaMercado": 10, "plazoFinanciacion": 12, "provisionRegistrada": 2000,
                   "tasas": {"pv": 1, "t30": 3, "t60": 8, "t90": 15, "t180": 30, "t360": 60, "tmax": 100}},
    "datasets": {"cartera": [
        _ej("F-001", "Comercial Alfa", "2025-12-10", "2026-01-09", "12000", cobro="12000", fecha_cobro="2026-01-08", confirmado="12000", despacho="2025-12-10"),
        _ej("F-002", "Distribuidora Beta", "2025-12-28", "2026-01-27", "8000", despacho="2026-01-05", importe="8000"),
        _ej("F-003", "Gama Cía. Ltda.", "2025-11-15", "2025-12-15", "5000", cobro="5000", fecha_cobro="2026-01-20"),
        _ej("F-004", "Delta S.A.", "2025-10-01", "2025-10-31", "4000", cobro="1000", fecha_cobro="2026-02-10", confirmado="3500"),
        _ej("F-005", "Épsilon S.A.", "2025-09-01", "2025-10-01", "3000", tasa_individual="50"),
        _ej("F-006", "Zeta Hnos.", "2025-04-01", "2025-05-01", "2500"),
        _ej("F-007", "Eta Comercial", "2024-06-01", "2024-07-01", "1500"),
        _ej("F-008", "Theta Industrial", "2025-07-01", "2027-07-01", "20000", confirmado="20000", despacho="2025-06-30"),
        _ej("F-009", "Iota Market", "2025-11-20", "2025-12-20", "6000", cobro="6000", fecha_cobro="2025-12-30"),
        _ej("F-010", "Kappa Retail", "2025-11-01", "2025-12-01", "2000"),
        _ej("F-011", "Lambda S.A.", "2025-10-15", "2025-11-14", "3500", cobro="3500", fecha_cobro="2026-01-15"),
        _ej("F-012", "Mu Ventas", "2025-12-05", "2026-01-04", "-500"),
    ]},
}

_SIN_TASA = {**EJEMPLO["parametros"], "tasaMercado": None, "tasas": {"pv": 1, "t30": 3, "t90": 15, "t180": 30, "t360": 60, "tmax": 100},
             "descuentoRegistrado": 500}
ESCENARIOS = [
    ("niif_completas", EJEMPLO["datasets"], EJEMPLO["parametros"], EJEMPLO["corte"]),
    ("pymes_2015", EJEMPLO["datasets"], {**EJEMPLO["parametros"], "_marco": MARCO_PYMES, "_edicion": "2015"}, EJEMPLO["corte"]),
    ("pymes_2025_sin_tasa", EJEMPLO["datasets"], {**_SIN_TASA, "_marco": MARCO_PYMES, "_edicion": "2025"}, EJEMPLO["corte"]),
    ("completas_reversion", EJEMPLO["datasets"], {**EJEMPLO["parametros"], "provisionRegistrada": 9000, "descuentoRegistrado": 1000}, EJEMPLO["corte"]),
]
